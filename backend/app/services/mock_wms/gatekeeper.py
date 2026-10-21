import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models.shipment import Shipment
from app.models.validation import Discrepancy, WMSTransmission
from app.models.wms import WMSReceipt, WMSReceiptItem
from app.schemas.wms import WMSInboundReceiptPayload
from app.services.export.payload_builder import payload_builder


class WMSService:
    """
    Gatekeeper and Mock WMS Integration Engine.
    - Strictly locks transmission unless all validations pass and supervisor approval is signed.
    - Accepts typed WMS payload and persists real Inbound Receipts with line items.
    - Idempotent: duplicate submissions return existing receipt without creating duplicate lines.
    - Simulates failures safely without creating inconsistent receipt records.
    - Logs every API attempt, payload, response code and response body.
    """

    def check_transmission_eligibility(self, db: Session, shipment_id: str) -> Dict[str, Any]:
        shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
        if not shipment:
            return {"eligible": False, "reason": "Lô hàng không tồn tại."}

        # 1. Kiểm tra trạng thái đối soát (phải là VALIDATED hoặc không có lỗi ERROR)
        blocking_errors = db.query(Discrepancy).filter(
            Discrepancy.shipment_id == shipment_id,
            Discrepancy.severity == "ERROR",
            Discrepancy.status == "OPEN"
        ).count()

        if blocking_errors > 0 or shipment.status == "DISCREPANT":
            return {
                "eligible": False,
                "reason": f"Không thể truyền WMS: Còn {blocking_errors} lỗi bất đồng bộ nghiêm trọng chưa được xử lý.",
            }

        # 2. Kiểm tra chữ ký phê duyệt (Supervisor Approval)
        if shipment.approval_status != "APPROVED":
            return {
                "eligible": False,
                "reason": "Không thể truyền WMS: Lô hàng chưa nhận được chữ ký phê duyệt (Supervisor Approval).",
            }

        from app.services.validation.reconciler import reconciliation_engine
        summary = reconciliation_engine.reconcile_shipment(db, shipment_id, persist=False)
        if summary["error_count"] or shipment.status not in ("VALIDATED", "APPROVED", "TRANSMITTED"):
            return {"eligible": False, "reason": "Hồ sơ chưa hợp lệ; hãy trích xuất và đối soát đầy đủ bộ chứng từ theo nguồn nhập."}

        return {"eligible": True, "reason": "Đủ điều kiện truyền dữ liệu vào hệ thống kho."}

    def process_mock_inbound_receipt(
        self,
        db: Session,
        payload: WMSInboundReceiptPayload,
        simulate_failure: bool = False
    ) -> Dict[str, Any]:
        """
        Mock WMS Inbound Endpoint logic:
        1. Xử lý lỗi giả lập nếu được bật (simulate_failure=True): ném lỗi mà không tạo phiếu rác.
        2. Idempotency: Kiểm tra nếu receipt_id hoặc (shipment_code, customs_declaration_no) đã tồn tại.
        3. Tạo mới và lưu trữ phiếu nhập kho (WMSReceipt) và chi tiết SKU vào DB.
        """
        # 1. Mô phỏng lỗi hệ thống WMS (Simulated 503 Failure)
        if simulate_failure:
            raise RuntimeError(
                "WMS_SIMULATED_FAILURE: Máy chủ WMS phản hồi lỗi HTTP 503 Service Unavailable "
                "(Mô phỏng sự cố mạng/hệ thống WMS). Giao dịch bị hủy và không tạo phiếu nhập."
            )

        # 2. Idempotency Check (Chống tạo trùng lặp phiếu nhập kho)
        idempotency_key = f"{payload.shipment_code}:{payload.customs_declaration_no}".strip()
        existing = db.query(WMSReceipt).filter(
            (WMSReceipt.receipt_number == payload.receipt_id) | 
            (WMSReceipt.idempotency_key == idempotency_key)
        ).first()

        if existing:
            return {
                "receipt_id": existing.receipt_number,
                "status": "ALREADY_RECEIVED",
                "is_duplicate": True,
                "message": f"Phiếu nhập {existing.receipt_number} đã tồn tại trong hệ thống WMS (Idempotent response - không tạo phiếu trùng lặp).",
                "receipt_id_pk": existing.id,
                "created_at": existing.created_at.isoformat()
            }

        # Tìm shipment_id liên kết nếu có
        shipment = db.query(Shipment).filter(Shipment.shipment_code == payload.shipment_code).first()
        shipment_id = shipment.id if shipment else None

        # Tính tổng giá trị phiếu nhập
        total_val = sum((item.unit_price or 0.0) * (item.quantity or 0.0) for item in payload.line_items)

        # 3. Tạo mới persistent WMSReceipt
        receipt = WMSReceipt(
            receipt_number=payload.receipt_id,
            idempotency_key=idempotency_key,
            shipment_id=shipment_id,
            shipment_code=payload.shipment_code,
            customs_declaration_no=payload.customs_declaration_no,
            warehouse_type=payload.warehouse_type or "BONDED",
            warehouse_name=shipment.bonded_warehouse_name if shipment else "Kho Ngoại Quan Đình Vũ",
            status="RECEIVED",
            receipt_date=payload.receipt_date,
            shipper=payload.shipper,
            consignee=payload.consignee,
            carrier_vessel=payload.carrier_vessel,
            containers_json=json.dumps(payload.containers or [], ensure_ascii=False),
            seals_json=json.dumps(payload.seals or [], ensure_ascii=False),
            total_packages=payload.total_packages,
            total_gross_weight_kg=payload.total_gross_weight_kg,
            total_line_items=len(payload.line_items),
            total_value=total_val,
            currency=payload.line_items[0].currency if payload.line_items else "USD",
        )
        db.add(receipt)
        db.flush()

        # Thêm từng dòng hàng SKU (Bảo toàn số 0 ở đầu của SKU và Mã HS)
        for item in payload.line_items:
            unit_p = float(item.unit_price) if item.unit_price is not None else 0.0
            qty = float(item.quantity) if item.quantity is not None else 0.0
            tot_amt = unit_p * qty

            bin_loc = f"RACK-{(item.line_number - 1) // 10 + 1:02d}-{(item.line_number - 1) % 10 + 1:02d}"

            rcpt_item = WMSReceiptItem(
                receipt_id=receipt.id,
                line_number=item.line_number,
                sku=str(item.sku).strip(),
                part_number=str(item.part_number).strip() if item.part_number else None,
                item_description=str(item.item_description).strip(),
                hs_code=str(item.hs_code).strip() if item.hs_code else None,
                quantity=qty,
                uom=str(item.uom).strip().upper(),
                unit_price=unit_p,
                total_amount=tot_amt,
                currency=str(item.currency or "USD").strip().upper(),
                po_number=str(item.po_number).strip() if item.po_number else None,
                customs_declaration_no=str(item.customs_declaration_no or payload.customs_declaration_no).strip(),
                net_weight_kg=float(item.net_weight_kg) if item.net_weight_kg is not None else None,
                gross_weight_kg=float(item.gross_weight_kg) if item.gross_weight_kg is not None else None,
                bin_location=bin_loc,
                notes="Nhập kho ngoại quan từ AI Gateway"
            )
            db.add(rcpt_item)

        db.commit()
        db.refresh(receipt)

        return {
            "receipt_id": receipt.receipt_number,
            "status": "RECEIVED",
            "is_duplicate": False,
            "message": f"Tạo mới thành công phiếu nhập kho {receipt.receipt_number} với {len(payload.line_items)} dòng hàng.",
            "receipt_id_pk": receipt.id,
            "created_at": receipt.created_at.isoformat()
        }

    def transmit_to_wms(
        self,
        db: Session,
        shipment_id: str,
        approved_by: str,
        simulate_failure: bool = False
    ) -> WMSTransmission:
        """
        Truyền hồ sơ lô hàng đã phê duyệt vào WMS.
        Ghi log đầy đủ mọi lượt truyền (payload, response code, response body, lỗi).
        """
        eligibility = self.check_transmission_eligibility(db, shipment_id)
        if not eligibility["eligible"]:
            raise PermissionError(eligibility["reason"])

        shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
        if not shipment:
            raise ValueError("Không tìm thấy lô hàng.")

        payload = payload_builder.build_inbound_receipt_payload(db, shipment)
        payload_json = json.dumps(payload.model_dump(), ensure_ascii=False)

        now = datetime.utcnow()

        try:
            # Gửi payload vào engine Mock WMS Receiver
            wms_res = self.process_mock_inbound_receipt(db, payload, simulate_failure=simulate_failure)
            
            transmission = WMSTransmission(
                shipment_id=shipment_id,
                status="TRANSMITTED",
                is_blocked=False,
                approved_by=approved_by,
                approved_at=now,
                payload_json=payload_json,
                wms_endpoint="/api/v1/wms/mock/inbound-receipts",
                transmitted_at=now,
                wms_response_code=200,
                wms_response_body=json.dumps(wms_res, ensure_ascii=False)
            )
            db.add(transmission)
            shipment.status = "TRANSMITTED"
            db.commit()
            db.refresh(transmission)
            return transmission

        except Exception as exc:
            # Ghi nhận log thất bại nhưng không làm hỏng trạng thái lô hàng
            transmission = WMSTransmission(
                shipment_id=shipment_id,
                status="FAILED",
                is_blocked=False,
                approved_by=approved_by,
                approved_at=now,
                payload_json=payload_json,
                wms_endpoint="/api/v1/wms/mock/inbound-receipts",
                transmitted_at=now,
                wms_response_code=503 if "SIMULATED" in str(exc) else 500,
                wms_response_body=json.dumps({"error": str(exc)}, ensure_ascii=False)
            )
            db.add(transmission)
            db.commit()
            db.refresh(transmission)
            raise exc

    def list_mock_receipts(self, db: Session, skip: int = 0, limit: int = 50) -> List[WMSReceipt]:
        """Lấy danh sách các phiếu nhập kho đã được tạo trong Mock WMS."""
        return db.query(WMSReceipt).order_by(WMSReceipt.created_at.desc()).offset(skip).limit(limit).all()

    def get_mock_receipt(self, db: Session, receipt_id: str) -> Optional[WMSReceipt]:
        """Lấy chi tiết 1 phiếu nhập kho theo id hoặc receipt_number."""
        return db.query(WMSReceipt).filter(
            (WMSReceipt.id == receipt_id) | (WMSReceipt.receipt_number == receipt_id)
        ).first()

    def get_shipment_transmissions(self, db: Session, shipment_id: str) -> List[WMSTransmission]:
        """Lấy toàn bộ lịch sử các lượt truyền WMS của một lô hàng."""
        return db.query(WMSTransmission).filter(
            WMSTransmission.shipment_id == shipment_id
        ).order_by(WMSTransmission.created_at.desc()).all()


wms_service = WMSService()

