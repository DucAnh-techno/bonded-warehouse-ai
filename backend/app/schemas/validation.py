from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict


class DiscrepancyResponse(BaseModel):
    id: str
    shipment_id: str
    rule_code: str
    severity: str  # ERROR | WARNING
    category: Optional[str] = "CONFLICT"  # MISSING | CONFLICT | NOT_APPLICABLE | NOT_VERIFIED
    field_name: str
    description_vi: str
    source_doc_a_id: Optional[str] = None
    source_doc_a_name: Optional[str] = None
    value_a: Optional[str] = None
    source_doc_b_id: Optional[str] = None
    source_doc_b_name: Optional[str] = None
    value_b: Optional[str] = None
    status: str  # OPEN | OVERRIDDEN | ACCEPTED | REJECTED
    resolution_action: Optional[str] = None
    resolution_reason: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DiscrepancyResolutionRequest(BaseModel):
    action: str  # OVERRIDE | ACCEPT_WITH_REASON | REJECT
    reason: str  # Mandatory audit reason in Vietnamese
    override_value: Optional[str] = None
    resolved_by: str = "operator"


class ReconciledSkuComparison(BaseModel):
    po_reference: Optional[str] = None
    sku: str
    description_vi: str
    hs_code_declaration: Optional[str] = None
    hs_code_invoice: Optional[str] = None
    qty_declaration: Optional[float] = None
    qty_invoice: Optional[float] = None
    qty_packing_list: Optional[float] = None
    qty_po: Optional[float] = None
    unit_price_invoice: Optional[float] = None
    uom: Optional[str] = None
    is_matched: bool = True
    discrepancies: List[str] = []


class ReconciliationMatrixResponse(BaseModel):
    shipment_id: str
    shipment_code: str
    total_skus: int
    matched_skus: int
    error_count: int
    warning_count: int
    validation_status: str
    sku_matrix: List[ReconciledSkuComparison]
    discrepancies: List[DiscrepancyResponse]


class RuleSettingResponse(BaseModel):
    rule_code: str
    name_vi: str
    description_vi: str
    severity: str
    enabled: bool
    tolerance: Optional[float] = None
    category: str
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RuleSettingUpdate(BaseModel):
    enabled: Optional[bool] = None
    tolerance: Optional[float] = None
    severity: Optional[str] = None


class ShipmentApprovalRequest(BaseModel):
    approved_by: str
    notes: Optional[str] = None


class ShipmentApprovalResponse(BaseModel):
    success: bool
    shipment_id: str
    status: str
    approval_status: str
    is_blocked: bool
    blocking_reasons: List[str] = []
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    message_vi: str

