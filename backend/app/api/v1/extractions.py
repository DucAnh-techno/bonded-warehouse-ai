import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.demo_limits import extraction_budget
from app.models.shipment import Shipment
from app.models.document import Document
from app.models.extraction import DocumentExtraction, ExtractedLineItem
from app.models.audit import AuditLog
from app.models.validation import Discrepancy
from app.schemas.extraction import (
    DocumentExtractionResponse, 
    ExtractedLineItemResponse, 
    ExtractedLineItemUpdate,
    BatchShipmentReconciliationResult,
)
from app.services import storage_service, gemini_extractor, reconciliation_engine
from app.services.validation.documents import invalidate_approval, latest_documents

router = APIRouter(prefix="/extractions", tags=["Extractions"])

NON_SKU_PATTERNS = (
    "DETAILS AS PER BILL OF LADING",
    "SAID TO CONTAIN",
    "AS PER B/L",
    "AS PER BILL OF LADING",
    "CARGO AS PER",
)


@router.post("/extract/{document_id}", response_model=DocumentExtractionResponse, dependencies=[Depends(extraction_budget)])
async def extract_document_data(document_id: str, db: Session = Depends(get_db)):
    """
    Kích hoạt tiến trình trích xuất tài liệu thật với Google Gemini Multimodal API.
    Tuyệt đối không giả lập dữ liệu (No mock). Nếu lỗi API sẽ trả về lỗi chi tiết.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy chứng từ.")

    invalidate_approval(doc.shipment)
    db.commit()
    abs_path = storage_service.get_absolute_path(doc.storage_path)
    if not abs_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tệp chứng từ không tồn tại trên bộ lưu trữ.")

    def save_failure(message: str):
        failed = db.query(DocumentExtraction).filter_by(document_id=doc.id).first()
        if failed is None:
            failed = DocumentExtraction(document_id=doc.id, model_name=gemini_extractor.model_name, raw_response_json="{}")
            db.add(failed)
        failed.status = "FAILED"
        failed.error_message = message
        db.commit()
        if doc.shipment_id:
            reconciliation_engine.reconcile_shipment(db, doc.shipment_id, trigger_reason="Extraction failed")

    try:
        # Gọi Gemini Multimodal API (thật)
        extraction_result, token_usage = await gemini_extractor.extract_document(
            file_path=abs_path,
            mime_type=doc.mime_type,
            document_type_hint=doc.document_type
        )
    except ValueError as ve:
        save_failure(str(ve))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        save_failure("Gemini chưa xử lý được chứng từ. Vui lòng thử lại.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gemini chưa xử lý được chứng từ (kết nối, hạn mức hoặc dữ liệu). Vui lòng thử lại."
        )

    header_payload = {
        "document_type_detected": extraction_result.document_type_detected,
        "document_number": extraction_result.document_number,
        "issue_date": extraction_result.issue_date,
        "shipper": extraction_result.shipper_exporter,
        "consignee": extraction_result.consignee_importer,
        "buyer_name": extraction_result.buyer_name,
        "cargo_owner_name": extraction_result.cargo_owner_name,
        "supplier_name": extraction_result.supplier_name,
        "warehouse_name": extraction_result.warehouse_name,
        "tenant_name": extraction_result.tenant_name,
        "lessor_name": extraction_result.lessor_name,
        "valid_from": extraction_result.valid_from,
        "valid_until": extraction_result.valid_until,
        "port_of_discharge": extraction_result.port_of_discharge,
        "vessel_voyage": extraction_result.vessel_voyage,
        "eta": extraction_result.eta,
        "commodity_description": extraction_result.commodity_description,
        "container_numbers": extraction_result.container_numbers,
        "seal_numbers": extraction_result.seal_numbers,
        "total_gross_weight_kg": extraction_result.total_gross_weight_kg,
        "total_net_weight_kg": extraction_result.total_net_weight_kg,
        "measurement_cbm": extraction_result.measurement_cbm,
        "total_packages": extraction_result.total_packages,
        "package_unit": extraction_result.package_unit,
        "total_invoice_value": extraction_result.total_invoice_value,
        "currency": extraction_result.currency,
        "incoterms": extraction_result.incoterms,
        "contract_number_ref": extraction_result.contract_number_ref,
        "invoice_number_ref": extraction_result.invoice_number_ref,
        "po_numbers": extraction_result.po_numbers,
    }

    # Lưu kết quả riêng biệt cho từng chứng từ (Granular Document Extraction Storage)
    extraction = db.query(DocumentExtraction).filter(DocumentExtraction.document_id == document_id).first()
    if not extraction:
        extraction = DocumentExtraction(
            document_id=document_id,
            model_name=gemini_extractor.model_name,
            raw_response_json=json.dumps(extraction_result.model_dump(), ensure_ascii=False),
            status="SUCCESS",
            prompt_tokens=token_usage.get("prompt_tokens"),
            candidate_tokens=token_usage.get("candidate_tokens"),
            extracted_header_json=json.dumps(header_payload, ensure_ascii=False)
        )
        db.add(extraction)
        db.flush()
    else:
        extraction.version += 1
        extraction.model_name = gemini_extractor.model_name
        extraction.raw_response_json = json.dumps(extraction_result.model_dump(), ensure_ascii=False)
        extraction.status = "SUCCESS"
        extraction.error_message = None
        extraction.prompt_tokens = token_usage.get("prompt_tokens")
        extraction.candidate_tokens = token_usage.get("candidate_tokens")
        extraction.extracted_header_json = json.dumps(header_payload, ensure_ascii=False)
        # Xóa các dòng hàng cũ để lưu bộ mới
        for li in list(extraction.line_items):
            db.delete(li)
        db.flush()

    # Cập nhật số tờ khai cho lô hàng nếu trích xuất được từ Tờ khai HQ
    if extraction_result.document_number and (doc.document_type == "CUSTOMS_DECLARATION" or extraction_result.document_type_detected == "CUSTOMS_DECLARATION"):
        if doc.shipment and not doc.shipment.customs_declaration_no:
            doc.shipment.customs_declaration_no = extraction_result.document_number

    # Lưu danh sách SKU items (Chứng từ vận tải B/L và Thông báo hàng đến Arrival Notice không có SKU chi tiết)
    NON_SKU_PATTERNS = (
        "DETAILS AS PER BILL OF LADING",
        "SAID TO CONTAIN",
        "AS PER B/L",
        "AS PER BILL OF LADING",
        "CARGO AS PER",
    )
    is_transport_doc = (
        doc.document_type in ("BILL_OF_LADING", "ARRIVAL_NOTICE", "WAREHOUSE_CONTRACT")
        or extraction_result.document_type_detected in ("BILL_OF_LADING", "ARRIVAL_NOTICE", "WAREHOUSE_CONTRACT")
        or "ARRIVAL" in (doc.original_filename or "").upper()
    )

    if not is_transport_doc:
        for item in extraction_result.items:
            desc_upper = (item.description_vi or "").upper()
            sku_upper = (item.sku or "").upper()
            if any(pat in desc_upper or pat in sku_upper for pat in NON_SKU_PATTERNS):
                continue

            line_item = ExtractedLineItem(
                extraction_id=extraction.id,
                item_index=item.item_index,
                sku=item.sku,
                part_number=item.part_number,
                description_vi=item.description_vi,
                hs_code=item.hs_code,
                quantity=item.quantity,
                uom=item.uom,
                unit_price=item.unit_price,
                total_amount=item.total_amount,
                currency=item.currency,
                gross_weight_kg=item.gross_weight_kg,
                net_weight_kg=item.net_weight_kg,
                po_reference=item.po_reference,
                page_number=item.page_number or 1,
                raw_line_text=item.raw_line_text
            )
            db.add(line_item)

    db.commit()
    db.refresh(extraction)

    # Kích hoạt động cơ đối soát tất định của lô hàng cha
    if doc.shipment_id:
        try:
            reconciliation_engine.reconcile_shipment(db, doc.shipment_id, trigger_reason=f"Doc {doc.original_filename} Extracted by Gemini")
        except Exception as e:
            print(f"Warning: Reconcile trigger failed: {e}")

    return extraction


@router.get("/document/{document_id}", response_model=DocumentExtractionResponse)
def get_document_extraction(document_id: str, db: Session = Depends(get_db)):
    """Lấy dữ liệu trích xuất của một chứng từ cụ thể."""
    extraction = db.query(DocumentExtraction).filter(DocumentExtraction.document_id == document_id).first()
    if not extraction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chứng từ chưa được trích xuất dữ liệu qua AI.")
    return extraction


@router.patch("/items/{item_id}", response_model=ExtractedLineItemResponse)
def update_extracted_item(
    item_id: str,
    payload: ExtractedLineItemUpdate,
    user_id: str = "operator",
    db: Session = Depends(get_db)
):
    """
    Chỉnh sửa thủ công dữ liệu dòng hàng do AI trích xuất (HITL Field Editing).
    Tự động ghi nhận lịch sử vào AuditLog và kích hoạt tái đối soát tự động.
    """
    item = db.query(ExtractedLineItem).filter(ExtractedLineItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy dòng hàng trích xuất.")

    shipment_id = None
    if item.extraction and item.extraction.document:
        shipment_id = item.extraction.document.shipment_id

    invalidate_approval(item.extraction.document.shipment)
    update_dict = payload.model_dump(exclude_unset=True, exclude={"reason"})
    if any(update_dict.get(k, "valid") is None for k in ("description_vi", "item_index")):
        raise HTTPException(422, "Mô tả dòng hàng không được để null.")
    reason = payload.reason or "Chỉnh sửa dữ liệu trích xuất thủ công"

    for field_name, new_val in update_dict.items():
        old_val = getattr(item, field_name)
        if str(old_val) != str(new_val):
            # Record audit trail
            if shipment_id:
                audit = AuditLog(
                    shipment_id=shipment_id,
                    action="FIELD_OVERRIDE",
                    target_entity="ExtractedLineItem",
                    target_id=item.id,
                    field_name=field_name,
                    old_value=str(old_val) if old_val is not None else None,
                    new_value=str(new_val) if new_val is not None else None,
                    user_id=user_id,
                    reason=reason,
                )
                db.add(audit)
            setattr(item, field_name, new_val)

    db.commit()
    db.refresh(item)

    # Dynamic Revalidation: Tự động chạy lại quy tắc đối soát
    if shipment_id:
        try:
            reconciliation_engine.reconcile_shipment(
                db, 
                shipment_id, 
                trigger_reason=f"Line Item {item.sku or item.item_index} manually corrected"
            )
        except Exception as e:
            print(f"Warning: Dynamic revalidation failed: {e}")

    return item


@router.get("/items/{item_id}/audit-history")
def get_item_audit_history(item_id: str, db: Session = Depends(get_db)):
    """Lấy toàn bộ lịch sử chỉnh sửa / điều chỉnh của một dòng hàng."""
    logs = db.query(AuditLog).filter(
        AuditLog.target_id == item_id,
        AuditLog.target_entity == "ExtractedLineItem"
    ).order_by(AuditLog.timestamp.desc()).all()

    return [
        {
            "id": log.id,
            "field_name": log.field_name,
            "old_value": log.old_value,
            "new_value": log.new_value,
            "user_id": log.user_id,
            "reason": log.reason,
            "timestamp": log.timestamp.isoformat(),
        }
        for log in logs
    ]


@router.post("/shipment/{shipment_id}/batch-reconcile", response_model=BatchShipmentReconciliationResult, dependencies=[Depends(extraction_budget)])
async def batch_reconcile_shipment(shipment_id: str, db: Session = Depends(get_db)):
    """
    Trích xuất và đối chiếu toàn bộ giấy tờ hiện có của lô hàng trong 1 prompt duy nhất
    qua Google Gemini Multimodal API, đồng thời kiểm tra tính hợp lệ của bộ hồ sơ.
    """
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lô hàng.")

    if not shipment.documents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lô hàng chưa có tài liệu nào để đối soát.")

    # Prepare document file parts
    invalidate_approval(shipment)
    db.commit()
    doc_payloads = []
    for doc in latest_documents(shipment.documents):
        abs_path = storage_service.get_absolute_path(doc.storage_path)
        if abs_path.exists():
            cached_data = None
            if doc.extraction and doc.extraction.status == "SUCCESS" and doc.extraction.raw_response_json:
                try:
                    raw_d = json.loads(doc.extraction.raw_response_json)
                    if isinstance(raw_d, dict) and raw_d.get("document_type_detected"):
                        cached_data = raw_d
                except Exception:
                    cached_data = None
            doc_payloads.append({
                "doc_id": doc.id,
                "filename": doc.original_filename,
                "document_type": doc.document_type,
                "mime_type": doc.mime_type,
                "file_path": abs_path,
                "cached_extraction": cached_data,
            })

    if not doc_payloads:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Không tìm thấy tệp chứng từ vật lý trên máy chủ.")

    def save_batch_failure(message: str):
        for payload in doc_payloads:
            failed = db.query(DocumentExtraction).filter_by(document_id=payload["doc_id"]).first()
            if failed is None:
                failed = DocumentExtraction(document_id=payload["doc_id"], model_name=gemini_extractor.model_name, raw_response_json="{}")
                db.add(failed)
            failed.status = "FAILED"
            failed.error_message = message
        db.commit()
        reconciliation_engine.reconcile_shipment(db, shipment.id, trigger_reason="Batch extraction failed")

    try:
        reconcile_result, token_usage = await gemini_extractor.batch_extract_and_reconcile_shipment(
            documents=doc_payloads,
            shipment_code=shipment.shipment_code
        )
    except ValueError as ve:
        save_batch_failure(str(ve))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        save_batch_failure("Gemini chưa xử lý được hồ sơ. Vui lòng thử lại.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gemini chưa xử lý được chứng từ (kết nối, hạn mức hoặc dữ liệu). Vui lòng thử lại.")

    expected_ids = {d["doc_id"] for d in doc_payloads}
    returned_ids = [d.document_id for d in reconcile_result.documents]
    if set(returned_ids) != expected_ids or len(returned_ids) != len(expected_ids):
        save_batch_failure("Gemini trả thiếu, trùng hoặc sai mã chứng từ.")
        raise HTTPException(502, "Gemini trả thiếu, trùng hoặc sai mã chứng từ. Hãy thử lại từng chứng từ.")

    # Update or create DocumentExtraction for each document returned
    doc_map = {doc.id: doc for doc in shipment.documents}
    name_map = {doc.original_filename.lower(): doc for doc in shipment.documents}

    for extracted_doc in reconcile_result.documents:
        target_doc = None
        if extracted_doc.document_id and extracted_doc.document_id in doc_map:
            target_doc = doc_map[extracted_doc.document_id]
        elif extracted_doc.document_id and extracted_doc.document_id.lower() in name_map:
            target_doc = name_map[extracted_doc.document_id.lower()]

        if not target_doc:
            continue

        header_data = {
            "document_type_detected": extracted_doc.document_type_detected,
            "document_number": extracted_doc.document_number,
            "issue_date": extracted_doc.issue_date,
            "shipper": extracted_doc.shipper_exporter,
            "consignee": extracted_doc.consignee_importer,
            "buyer_name": extracted_doc.buyer_name,
            "cargo_owner_name": extracted_doc.cargo_owner_name,
            "supplier_name": extracted_doc.supplier_name,
            "warehouse_name": extracted_doc.warehouse_name,
            "tenant_name": extracted_doc.tenant_name,
            "lessor_name": extracted_doc.lessor_name,
            "valid_from": extracted_doc.valid_from,
            "valid_until": extracted_doc.valid_until,
            "port_of_discharge": extracted_doc.port_of_discharge,
            "vessel_voyage": extracted_doc.vessel_voyage,
            "eta": extracted_doc.eta,
            "commodity_description": extracted_doc.commodity_description,
            "container_numbers": extracted_doc.container_numbers,
            "seal_numbers": extracted_doc.seal_numbers,
            "total_gross_weight_kg": extracted_doc.total_gross_weight_kg,
            "total_net_weight_kg": extracted_doc.total_net_weight_kg,
            "measurement_cbm": extracted_doc.measurement_cbm,
            "total_packages": extracted_doc.total_packages,
            "package_unit": extracted_doc.package_unit,
            "total_invoice_value": extracted_doc.total_invoice_value,
            "currency": extracted_doc.currency,
            "incoterms": extracted_doc.incoterms,
            "contract_number_ref": extracted_doc.contract_number_ref,
            "invoice_number_ref": extracted_doc.invoice_number_ref,
            "po_numbers": extracted_doc.po_numbers,
        }

        extraction = db.query(DocumentExtraction).filter(DocumentExtraction.document_id == target_doc.id).first()
        if not extraction:
            extraction = DocumentExtraction(
                document_id=target_doc.id,
                model_name=gemini_extractor.model_name,
                raw_response_json=json.dumps(extracted_doc.model_dump(), ensure_ascii=False),
                status="SUCCESS",
                prompt_tokens=token_usage.get("prompt_tokens"),
                candidate_tokens=token_usage.get("candidate_tokens"),
                extracted_header_json=json.dumps(header_data, ensure_ascii=False),
            )
            db.add(extraction)
            db.flush()
        else:
            extraction.version += 1
            extraction.model_name = gemini_extractor.model_name
            extraction.raw_response_json = json.dumps(extracted_doc.model_dump(), ensure_ascii=False)
            extraction.status = "SUCCESS"
            extraction.error_message = None
            extraction.prompt_tokens = token_usage.get("prompt_tokens")
            extraction.candidate_tokens = token_usage.get("candidate_tokens")
            extraction.extracted_header_json = json.dumps(header_data, ensure_ascii=False)
            for li in list(extraction.line_items):
                db.delete(li)
            db.flush()

        # Save SKU items (Chứng từ vận tải B/L và Thông báo hàng đến Arrival Notice không có SKU chi tiết)
        is_transport_doc = (
            target_doc.document_type in ("BILL_OF_LADING", "ARRIVAL_NOTICE", "WAREHOUSE_CONTRACT")
            or extracted_doc.document_type_detected in ("BILL_OF_LADING", "ARRIVAL_NOTICE", "WAREHOUSE_CONTRACT")
            or "ARRIVAL" in (target_doc.original_filename or "").upper()
        )

        if not is_transport_doc:
            for item in extracted_doc.items:
                desc_upper = (item.description_vi or "").upper()
                sku_upper = (item.sku or "").upper()
                if any(pat in desc_upper or pat in sku_upper for pat in NON_SKU_PATTERNS):
                    continue

                line_item = ExtractedLineItem(
                    extraction_id=extraction.id,
                    item_index=item.item_index,
                    sku=item.sku,
                    part_number=item.part_number,
                    description_vi=item.description_vi,
                    hs_code=item.hs_code,
                    quantity=item.quantity,
                    uom=item.uom,
                    unit_price=item.unit_price,
                    total_amount=item.total_amount,
                    currency=item.currency,
                    gross_weight_kg=item.gross_weight_kg,
                    net_weight_kg=item.net_weight_kg,
                    po_reference=item.po_reference,
                    page_number=item.page_number or 1,
                    raw_line_text=item.raw_line_text,
                )
                db.add(line_item)

    if reconcile_result.customs_declaration_no and not shipment.customs_declaration_no:
        shipment.customs_declaration_no = reconcile_result.customs_declaration_no

    db.commit()

    summary = reconciliation_engine.reconcile_shipment(db, shipment.id, trigger_reason="Batch extraction completed")
    reconcile_result.overall_validity = "INVALID" if summary["error_count"] else "VALID"
    reconcile_result.validity_reason = f"Đối soát xác định: {summary['error_count']} lỗi."
    reconcile_result.discrepancies = []
    return reconcile_result


@router.patch("/document/{document_id}/header", response_model=DocumentExtractionResponse)
def update_header(document_id: str, payload: dict = Body(...), db: Session = Depends(get_db)):
    extraction = db.query(DocumentExtraction).filter_by(document_id=document_id).first()
    if extraction is None:
        raise HTTPException(404, "Chứng từ chưa có kết quả trích xuất.")
    reason = str(payload.get("reason") or "").strip()
    if not reason:
        raise HTTPException(422, "Vui lòng ghi lý do sửa.")
    values = payload.get("values", {})
    allowed = {
        "document_number", "consignee", "buyer_name", "cargo_owner_name", "tenant_name",
        "lessor_name", "warehouse_name", "valid_from", "valid_until", "total_invoice_value",
        "shipper", "container_numbers", "seal_numbers", "total_packages", "package_unit",
        "total_gross_weight_kg", "total_net_weight_kg", "measurement_cbm", "eta",
        "port_of_discharge", "commodity_description", "vessel_voyage", "currency",
        "incoterms", "contract_number_ref", "invoice_number_ref", "po_numbers"
    }
    if not isinstance(values, dict) or set(values) - allowed:
        raise HTTPException(422, "Trường chỉnh sửa không hợp lệ.")
    from datetime import date
    import math
    for key, value in values.items():
        if value is None:
            continue
        if key in ("total_invoice_value", "total_gross_weight_kg", "total_net_weight_kg", "measurement_cbm"):
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise HTTPException(422, f"Trường {key} phải là số không âm.")
        elif key == "total_packages":
            if not isinstance(value, int) or value < 0:
                raise HTTPException(422, "Số kiện phải là số nguyên không âm.")
        elif key in ("container_numbers", "seal_numbers", "po_numbers"):
            if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
                raise HTTPException(422, f"Trường {key} phải là danh sách chuỗi.")
        elif isinstance(value, str):
            if len(value) > 500:
                raise HTTPException(422, f"Trường {key} tối đa 500 ký tự.")
        if key in ("valid_from", "valid_until", "eta"):
            try: date.fromisoformat(value)
            except (ValueError, TypeError): raise HTTPException(422, f"Trường {key} phải có định dạng YYYY-MM-DD.")
    header = json.loads(extraction.extracted_header_json or "{}")
    for key, value in values.items():
        if value != header.get(key):
            db.add(AuditLog(shipment_id=extraction.document.shipment_id, action="FIELD_OVERRIDE", target_entity="DocumentExtraction",
                target_id=extraction.id, field_name=key, old_value=str(header.get(key)), new_value=str(value), reason=reason))
            header[key] = value
    extraction.extracted_header_json = json.dumps(header, ensure_ascii=False)
    invalidate_approval(extraction.document.shipment)
    db.commit()
    reconciliation_engine.reconcile_shipment(db, extraction.document.shipment_id, trigger_reason="Header corrected")
    db.refresh(extraction)
    return extraction
