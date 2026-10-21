from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class ShipmentBase(BaseModel):
    shipment_code: Optional[str] = None
    customs_declaration_no: Optional[str] = None
    declaration_type: Optional[str] = "C11"
    warehouse_type: str = "BONDED"
    bonded_warehouse_name: Optional[str] = "Kho Ngoại Quan Đình Vũ - Hải Phòng"
    partner_name: Optional[str] = None
    direction: str = "INBOUND"
    inbound_source: Optional[str] = None  # DOMESTIC | FOREIGN
    entry_date: Optional[date] = None
    notes: Optional[str] = None


class ShipmentCreate(ShipmentBase):
    pass


class ShipmentUpdate(BaseModel):
    customs_declaration_no: Optional[str] = None
    declaration_type: Optional[str] = None
    warehouse_type: Optional[str] = None
    bonded_warehouse_name: Optional[str] = None
    partner_name: Optional[str] = None
    direction: Optional[str] = None
    inbound_source: Optional[str] = None
    entry_date: Optional[date] = None
    notes: Optional[str] = None
    model_config = ConfigDict(extra="forbid")


class ShipmentResponse(ShipmentBase):
    id: str
    status: str
    approval_status: str
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    document_count: int = 0
    discrepancy_count: int = 0
    requires_classification: bool = False

    model_config = ConfigDict(from_attributes=True)


class ShipmentStatsResponse(BaseModel):
    total_shipments: int
    draft_count: int
    reconciling_count: int
    discrepant_count: int
    validated_count: int
    approved_count: int
    transmitted_count: int
    inbound_count: int
    outbound_count: int


class FieldProvenance(BaseModel):
    value: Optional[str] = None
    source_document_name: Optional[str] = None
    source_document_type: Optional[str] = None
    source_document_id: Optional[str] = None


class CrossDocMatrixRow(BaseModel):
    field_key: str
    label_vi: str
    applicable_docs: List[str] = []  # ["BL", "AN", "SC", "INV", "PL", "TK", "HD"]
    values_by_doc: dict = {}         # {"BL": "...", "INV": "..."}
    status: str = "MISSING"          # MATCHED | MISMATCHED | WARNING | SINGLE_SOURCE | MISSING
    note_vi: Optional[str] = None


class ConsolidatedShipmentHeader(BaseModel):
    shipment_id: str
    shipment_code: str
    status: str
    approval_status: str
    inbound_source: Optional[str] = None
    requires_classification: bool = False
    entry_date: Optional[str] = None
    eta: Optional[FieldProvenance] = None
    port_of_discharge: Optional[FieldProvenance] = None
    supplier_name: Optional[FieldProvenance] = None
    commodity_description: Optional[FieldProvenance] = None
    package_unit: Optional[FieldProvenance] = None
    measurement_cbm: Optional[FieldProvenance] = None
    contract_no: Optional[FieldProvenance] = None
    tenant_name: Optional[FieldProvenance] = None
    lessor_name: Optional[FieldProvenance] = None
    valid_from: Optional[FieldProvenance] = None
    valid_until: Optional[FieldProvenance] = None
    customs_declaration_no: Optional[FieldProvenance] = None
    declaration_type: Optional[FieldProvenance] = None
    declaration_date: Optional[FieldProvenance] = None
    bill_of_lading_no: Optional[FieldProvenance] = None
    commercial_invoice_no: Optional[FieldProvenance] = None
    invoice_date: Optional[FieldProvenance] = None
    packing_list_no: Optional[FieldProvenance] = None
    po_numbers: List[str] = []
    shipper: Optional[FieldProvenance] = None
    consignee: Optional[FieldProvenance] = None
    warehouse_name: Optional[FieldProvenance] = None
    vessel_voyage: Optional[FieldProvenance] = None
    container_numbers: List[str] = []
    seal_numbers: List[str] = []
    total_packages: Optional[FieldProvenance] = None
    total_gross_weight_kg: Optional[FieldProvenance] = None
    total_net_weight_kg: Optional[FieldProvenance] = None
    total_invoice_value: Optional[FieldProvenance] = None
    currency: Optional[FieldProvenance] = None
    incoterms: Optional[FieldProvenance] = None
    document_values: Optional[dict] = None
    field_matrix: List[CrossDocMatrixRow] = []
    has_sale_contract: bool = False

