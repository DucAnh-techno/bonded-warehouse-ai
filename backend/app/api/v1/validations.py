from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.shipment import Shipment
from app.models.validation import Discrepancy, ValidationRuleSetting
from app.models.audit import AuditLog
from app.schemas.validation import (
    DiscrepancyResponse,
    DiscrepancyResolutionRequest,
    ReconciliationMatrixResponse,
    ReconciledSkuComparison,
    RuleSettingResponse,
    RuleSettingUpdate,
    ShipmentApprovalRequest,
    ShipmentApprovalResponse,
)
from app.services import reconciliation_engine
from app.services.validation.config import get_all_rule_settings

router = APIRouter(prefix="/validations", tags=["Validations"])


@router.get("/rules/config", response_model=List[RuleSettingResponse])
def get_rule_configurations(db: Session = Depends(get_db)):
    """Lấy danh sách cấu hình các quy tắc đối soát tất định và dung sai."""
    return get_all_rule_settings(db)


@router.put("/rules/config/{rule_code}", response_model=RuleSettingResponse)
def update_rule_configuration(
    rule_code: str,
    payload: RuleSettingUpdate,
    db: Session = Depends(get_db)
):
    """Bật/tắt quy tắc hoặc điều chỉnh ngưỡng dung sai (tolerance)."""
    setting = db.query(ValidationRuleSetting).filter(ValidationRuleSetting.rule_code == rule_code).first()
    if not setting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Không tìm thấy quy tắc {rule_code}")

    if payload.enabled is not None:
        setting.enabled = payload.enabled
    if payload.tolerance is not None:
        setting.tolerance = payload.tolerance
    if payload.severity is not None:
        setting.severity = payload.severity
    setting.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(setting)
    return setting


@router.get("/discrepancies/{shipment_id}", response_model=List[DiscrepancyResponse])
def get_shipment_discrepancies(shipment_id: str, db: Session = Depends(get_db)):
    """Lấy danh sách các bất đồng bộ (discrepancies) của một lô hàng."""
    return db.query(Discrepancy).filter(Discrepancy.shipment_id == shipment_id).all()


@router.post("/discrepancies/{discrepancy_id}/resolve", response_model=DiscrepancyResponse)
def resolve_discrepancy(
    discrepancy_id: str,
    payload: DiscrepancyResolutionRequest,
    db: Session = Depends(get_db)
):
    """
    Human-In-The-Loop resolution.
    Never automated. Requires explicit reason and audit recording.
    Triggers dynamic revalidation of shipment.
    """
    discrepancy = db.query(Discrepancy).filter(Discrepancy.id == discrepancy_id).first()
    if not discrepancy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bản ghi bất đồng bộ.")

    if not payload.reason.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bắt buộc phải nhập lý do nghiệp vụ cho việc giải quyết bất đồng bộ chứng từ."
        )

    discrepancy.status = payload.action  # OVERRIDDEN | ACCEPTED | REJECTED
    discrepancy.resolution_action = payload.action
    discrepancy.resolution_reason = payload.reason
    discrepancy.resolved_by = payload.resolved_by
    discrepancy.resolved_at = datetime.utcnow()

    # Immutable Audit Log
    audit = AuditLog(
        shipment_id=discrepancy.shipment_id,
        action="DISCREPANCY_RESOLVED",
        target_entity="Discrepancy",
        target_id=discrepancy.id,
        field_name=discrepancy.field_name,
        old_value=discrepancy.value_a,
        new_value=payload.override_value or discrepancy.value_b,
        user_id=payload.resolved_by,
        reason=f"Giải quyết xung đột {discrepancy.rule_code} ({payload.action}): {payload.reason}"
    )
    db.add(audit)
    db.commit()
    db.refresh(discrepancy)

    # Dynamic Revalidation triggered immediately
    reconciliation_engine.reconcile_shipment(
        db, discrepancy.shipment_id, trigger_reason=f"Discrepancy {discrepancy.rule_code} manually resolved"
    )

    return discrepancy


@router.get("/reconcile/{shipment_id}", response_model=ReconciliationMatrixResponse)
@router.post("/reconcile/{shipment_id}", response_model=ReconciliationMatrixResponse)
def run_shipment_reconciliation(shipment_id: str, request: Request, db: Session = Depends(get_db)):
    """Run full deterministic cross-document reconciliation for a shipment."""
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lô hàng.")

    recon_summary = reconciliation_engine.reconcile_shipment(db, shipment_id, trigger_reason="Manual Reconcile Request", persist=request.method != "GET")
    discrepancies = db.query(Discrepancy).filter(Discrepancy.shipment_id == shipment_id).all()

    sku_matrix = [ReconciledSkuComparison(**item) for item in recon_summary.get("sku_matrix", [])]
    matched_count = sum(1 for item in sku_matrix if item.is_matched)

    return ReconciliationMatrixResponse(
        shipment_id=shipment.id,
        shipment_code=shipment.shipment_code,
        total_skus=recon_summary["total_skus"],
        matched_skus=matched_count,
        error_count=recon_summary["error_count"],
        warning_count=recon_summary["warning_count"],
        validation_status=shipment.status,
        sku_matrix=sku_matrix,
        discrepancies=[DiscrepancyResponse.model_validate(d) for d in discrepancies]
    )


@router.post("/shipment/{shipment_id}/approve", response_model=ShipmentApprovalResponse)
def approve_shipment_validations(
    shipment_id: str,
    payload: ShipmentApprovalRequest,
    db: Session = Depends(get_db)
):
    """
    Gatekeeper phê duyệt lô hàng.
    Chặn phê duyệt (Block approval) nếu vẫn còn lỗi nghiêm trọng (severity == 'ERROR') chưa xử lý.
    """
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lô hàng.")

    reconciliation_engine.reconcile_shipment(db, shipment_id, trigger_reason="Approval check")
    if not payload.approved_by.strip():
        raise HTTPException(400, "Vui lòng nhập tên người duyệt.")
    open_errors = db.query(Discrepancy).filter(
        Discrepancy.shipment_id == shipment_id,
        Discrepancy.severity == "ERROR",
        Discrepancy.status == "OPEN"
    ).all()

    if open_errors or shipment.status == "DISCREPANT":
        error_msgs = [f"[{e.rule_code}] {e.description_vi}" for e in open_errors]
        return ShipmentApprovalResponse(
            success=False,
            shipment_id=shipment.id,
            status=shipment.status,
            approval_status=shipment.approval_status,
            is_blocked=True,
            blocking_reasons=error_msgs or ["Lô hàng đang ở trạng thái DISCREPANT."],
            approved_by=None,
            approved_at=None,
            message_vi=f"Không thể phê duyệt: Còn {len(open_errors)} lỗi bất đồng bộ nghiêm trọng (ERROR) cần được xử lý hoặc ghi đè (Override)."
        )

    # All blocking errors resolved -> approve
    now = datetime.utcnow()
    shipment.approval_status = "APPROVED"
    shipment.approved_by = payload.approved_by
    shipment.approved_at = now
    if payload.notes:
        shipment.notes = f"{shipment.notes or ''}\n[Phê duyệt {now.strftime('%d/%m/%Y %H:%M')} bởi {payload.approved_by}]: {payload.notes}".strip()

    audit = AuditLog(
        shipment_id=shipment.id,
        action="APPROVAL_GRANTED",
        target_entity="Shipment",
        target_id=shipment.id,
        user_id=payload.approved_by,
        reason=f"Phê duyệt hồ sơ đối soát lô hàng thành công. Ghi chú: {payload.notes or 'Hồ sơ đạt điều kiện.'}"
    )
    db.add(audit)
    db.commit()
    db.refresh(shipment)

    return ShipmentApprovalResponse(
        success=True,
        shipment_id=shipment.id,
        status=shipment.status,
        approval_status=shipment.approval_status,
        is_blocked=False,
        blocking_reasons=[],
        approved_by=shipment.approved_by,
        approved_at=shipment.approved_at,
        message_vi="Phê duyệt hồ sơ lô hàng thành công. Đủ điều kiện mở khóa truyền WMS."
    )
