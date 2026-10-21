from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict


class WMSLineItemPayload(BaseModel):
    line_number: int
    sku: str
    part_number: Optional[str] = None
    item_description: str
    hs_code: Optional[str] = None
    quantity: float
    uom: str
    po_number: Optional[str] = None
    customs_declaration_no: Optional[str] = None
    unit_price: Optional[float] = None
    currency: Optional[str] = None
    net_weight_kg: Optional[float] = None
    gross_weight_kg: Optional[float] = None


class WMSInboundReceiptPayload(BaseModel):
    receipt_id: str
    shipment_code: str
    customs_declaration_no: str
    warehouse_type: str = "BONDED"
    receipt_date: str
    shipper: Optional[str] = None
    consignee: Optional[str] = None
    carrier_vessel: Optional[str] = None
    containers: List[str] = []
    seals: List[str] = []
    total_packages: Optional[int] = None
    total_gross_weight_kg: Optional[float] = None
    total_line_items: int
    line_items: List[WMSLineItemPayload]


class WMSSyncRequest(BaseModel):
    approved_by: str
    approval_notes: Optional[str] = None
    simulate_failure: bool = False


class WMSMockReceiptResponse(BaseModel):
    receipt_id: str
    status: str
    is_duplicate: bool
    message: str
    receipt_id_pk: Optional[str] = None
    created_at: Optional[str] = None


class WMSReceiptItemResponse(BaseModel):
    id: str
    line_number: int
    sku: str
    part_number: Optional[str] = None
    item_description: str
    hs_code: Optional[str] = None
    quantity: float
    uom: str
    unit_price: Optional[float] = None
    total_amount: Optional[float] = None
    currency: str = "USD"
    po_number: Optional[str] = None
    customs_declaration_no: Optional[str] = None
    net_weight_kg: Optional[float] = None
    gross_weight_kg: Optional[float] = None
    bin_location: Optional[str] = None
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class WMSReceiptResponse(BaseModel):
    id: str
    receipt_number: str
    idempotency_key: str
    shipment_id: Optional[str] = None
    shipment_code: str
    customs_declaration_no: str
    warehouse_type: str = "BONDED"
    warehouse_name: Optional[str] = None
    status: str = "RECEIVED"
    receipt_date: str
    shipper: Optional[str] = None
    consignee: Optional[str] = None
    carrier_vessel: Optional[str] = None
    containers: List[str] = []
    seals: List[str] = []
    total_packages: Optional[int] = None
    total_gross_weight_kg: Optional[float] = None
    total_net_weight_kg: Optional[float] = None
    total_line_items: int = 0
    total_value: Optional[float] = None
    currency: str = "USD"
    created_at: datetime
    items: List[WMSReceiptItemResponse] = []

    model_config = ConfigDict(from_attributes=True)


class WMSTransmissionResponse(BaseModel):
    id: str
    shipment_id: str
    status: str
    is_blocked: bool
    blocking_reason: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    payload_json: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    wms_response_code: Optional[int] = None
    wms_response_body: Optional[str] = None
    transmitted_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


