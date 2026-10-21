import json
import urllib.parse
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.shipment import Shipment
from app.models.validation import WMSTransmission
from app.models.audit import AuditLog
from app.schemas.wms import (
    WMSSyncRequest,
    WMSTransmissionResponse,
    WMSInboundReceiptPayload,
    WMSMockReceiptResponse,
    WMSReceiptResponse,
)
from app.services import wms_service
from app.services.export import wms_excel_mapper, payload_builder

router = APIRouter(prefix="/wms", tags=["WMS Gateway"])


@router.get("/status/{shipment_id}")
def check_wms_status(shipment_id: str, db: Session = Depends(get_db)):
    """Gatekeeper status check: evaluates if shipment is permitted for transmission."""
    return wms_service.check_transmission_eligibility(db, shipment_id)


@router.post("/approve/{shipment_id}")
def approve_shipment_for_wms(
    shipment_id: str,
    payload: WMSSyncRequest,
    db: Session = Depends(get_db)
):
    """Supervisor approval step. Required before transmission or Excel export can unlock."""
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lô hàng.")

    from app.services.validation.reconciler import reconciliation_engine
    summary = reconciliation_engine.reconcile_shipment(db, shipment_id)
    if summary["error_count"] or not payload.approved_by.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể phê duyệt: Lô hàng vẫn còn lỗi bất đồng bộ chưa xử lý."
        )

    shipment.approval_status = "APPROVED"
    shipment.approved_by = payload.approved_by
    shipment.approved_at = datetime.utcnow()

    audit = AuditLog(
        shipment_id=shipment_id,
        action="WMS_APPROVAL",
        target_entity="Shipment",
        target_id=shipment_id,
        user_id=payload.approved_by,
        reason=f"Cán bộ phê duyệt chấp thuận chuyển tiếp dữ liệu WMS: {payload.approval_notes or 'Hồ sơ hợp lệ.'}"
    )
    db.add(audit)
    db.commit()

    return {"message": "Lô hàng đã được phê duyệt thành công để truyền WMS.", "approval_status": "APPROVED"}


@router.post("/transmit/{shipment_id}", response_model=WMSTransmissionResponse)
def transmit_to_wms(
    shipment_id: str,
    payload: WMSSyncRequest,
    db: Session = Depends(get_db)
):
    """
    Transmit validated & approved shipment into WMS.
    Hard gatekeeping: Blocked if not validated or not approved.
    Supports simulated failure via payload.simulate_failure.
    """
    try:
        transmission = wms_service.transmit_to_wms(
            db,
            shipment_id,
            approved_by=payload.approved_by,
            simulate_failure=payload.simulate_failure
        )
        
        parsed_payload = json.loads(transmission.payload_json) if transmission.payload_json else None
        return WMSTransmissionResponse(
            id=transmission.id,
            shipment_id=transmission.shipment_id,
            status=transmission.status,
            is_blocked=transmission.is_blocked,
            blocking_reason=transmission.blocking_reason,
            approved_by=transmission.approved_by,
            approved_at=transmission.approved_at,
            payload_json=transmission.payload_json,
            payload=parsed_payload,
            wms_response_code=transmission.wms_response_code,
            wms_response_body=transmission.wms_response_body,
            transmitted_at=transmission.transmitted_at,
            created_at=transmission.created_at
        )
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except RuntimeError as re:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(re))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/export-excel/{shipment_id}")
def export_wms_excel(shipment_id: str, db: Session = Depends(get_db)):
    """
    Export the shipment into the standardized 21-column WMS Inbound Excel sheet.
    Hard gatekeeping: Blocked if not validated or not approved.
    """
    try:
        shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
        if not shipment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lô hàng.")

        excel_bytes = wms_excel_mapper.generate_wms_excel(db, shipment_id)
        filename = f"WMS_Inbound_{shipment.shipment_code or shipment_id[:8]}.xlsx"
        quoted_filename = urllib.parse.quote(filename)

        return Response(
            content=excel_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={quoted_filename}; filename*=UTF-8''{quoted_filename}",
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/payload-preview/{shipment_id}", response_model=WMSInboundReceiptPayload)
def preview_wms_payload(shipment_id: str, db: Session = Depends(get_db)):
    """Preview standardized WMS inbound payload before transmission."""
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lô hàng.")
    return payload_builder.build_inbound_receipt_payload(db, shipment)


@router.post("/mock/inbound-receipts", response_model=WMSMockReceiptResponse)
def mock_receive_inbound_receipt(
    payload: WMSInboundReceiptPayload,
    simulate_failure: bool = Query(False, description="Simulate 503 WMS service unavailable"),
    db: Session = Depends(get_db)
):
    """
    Mock WMS endpoint accepting typed inbound receipt payload.
    Creates persistent receipt or idempotently returns existing receipt if already received.
    """
    try:
        res = wms_service.process_mock_inbound_receipt(db, payload, simulate_failure=simulate_failure)
        return WMSMockReceiptResponse(**res)
    except RuntimeError as re:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(re))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/mock/inbound-receipts", response_model=List[WMSReceiptResponse])
def list_mock_inbound_receipts(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """List persistent inbound receipts stored in the mock WMS database."""
    receipts = wms_service.list_mock_receipts(db, skip=skip, limit=limit)
    return receipts


@router.get("/mock/inbound-receipts/{receipt_id}", response_model=WMSReceiptResponse)
def get_mock_inbound_receipt(
    receipt_id: str,
    db: Session = Depends(get_db)
):
    """Get single mock WMS inbound receipt with its detailed line items."""
    receipt = wms_service.get_mock_receipt(db, receipt_id)
    if not receipt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiếu nhập kho WMS.")
    return receipt


@router.get("/transmissions/{shipment_id}", response_model=List[WMSTransmissionResponse])
def get_shipment_transmissions(
    shipment_id: str,
    db: Session = Depends(get_db)
):
    """Get all transmission attempts and audit logs for this shipment."""
    transmissions = wms_service.get_shipment_transmissions(db, shipment_id)
    results = []
    for t in transmissions:
        parsed_payload = None
        if t.payload_json:
            try:
                parsed_payload = json.loads(t.payload_json)
            except Exception:
                pass
        results.append(WMSTransmissionResponse(
            id=t.id,
            shipment_id=t.shipment_id,
            status=t.status,
            is_blocked=t.is_blocked,
            blocking_reason=t.blocking_reason,
            approved_by=t.approved_by,
            approved_at=t.approved_at,
            payload_json=t.payload_json,
            payload=parsed_payload,
            wms_response_code=t.wms_response_code,
            wms_response_body=t.wms_response_body,
            transmitted_at=t.transmitted_at,
            created_at=t.created_at
        ))
    return results
