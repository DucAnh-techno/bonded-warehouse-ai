from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# --- Structured Output Schema for Gemini API ---
class GeminiLineItemExtraction(BaseModel):
    item_index: int = Field(default=1, description="Số thứ tự dòng hàng")
    sku: Optional[str] = Field(None, description="Mã sản phẩm / Mã hàng hóa (SKU/Part No)")
    part_number: Optional[str] = Field(None, description="Mã phụ tùng hoặc ký hiệu nhà sản xuất nếu có")
    description_vi: str = Field(description="Mô tả hàng hóa bằng tiếng Việt hoặc tiếng Anh")
    hs_code: Optional[str] = Field(None, description="Mã số HS 8 chữ số (hoặc 4-6 số). Nếu không có ghi null, không đoán.")
    quantity: Optional[float] = Field(None, description="Số lượng thực tế hoặc khai báo")
    uom: Optional[str] = Field(None, description="Đơn vị tính: PCS, KG, BOX, SET, UNIT...")
    unit_price: Optional[float] = Field(None, description="Đơn giá")
    total_amount: Optional[float] = Field(None, description="Thành tiền = Số lượng x Đơn giá")
    currency: Optional[str] = Field(default=None, description="Loại tiền tệ (USD, VND, EUR...)")
    gross_weight_kg: Optional[float] = Field(None, description="Trọng lượng cả bì (kg)")
    net_weight_kg: Optional[float] = Field(None, description="Trọng lượng tịnh (kg)")
    po_reference: Optional[str] = Field(None, description="Số đơn đặt hàng PO tương ứng nếu có")
    page_number: Optional[int] = Field(default=1, description="Trang xuất hiện dòng hàng")
    raw_line_text: Optional[str] = Field(None, description="Nguyên văn dòng text hoặc ô dữ liệu trên chứng từ gốc")


class GeminiDocumentExtractionResult(BaseModel):
    document_type_detected: str = Field(description="Loại chứng từ: CUSTOMS_DECLARATION | COMMERCIAL_INVOICE | PACKING_LIST | BILL_OF_LADING | ARRIVAL_NOTICE | SALE_CONTRACT | PURCHASE_ORDER | CERT_OF_ORIGIN | WAREHOUSE_CONTRACT | OTHER")
    document_number: Optional[str] = Field(None, description="Số tờ khai / Số hóa đơn / Số Packing List / Số B/L / Số Hợp đồng SC / Số Arrival Notice")
    issue_date: Optional[str] = Field(None, description="Ngày phát hành (YYYY-MM-DD)")
    shipper_exporter: Optional[str] = Field(None, description="Người gửi hàng / Người xuất khẩu / Người bán (Seller trên SC)")
    consignee_importer: Optional[str] = Field(None, description="Người nhận hàng cuối cùng / Consignee (thường là Kho ngoại quan U&I)")
    buyer_name: Optional[str] = Field(None, description="Người mua hàng (Buyer) trên Sale Contract (SC) - chính là Chủ hàng / Khách hàng của kho U&I")
    cargo_owner_name: Optional[str] = Field(None, description="Chủ hàng / Người ủy thác trên Tờ khai hoặc SC nếu có")
    supplier_name: Optional[str] = Field(None, description="Tên nhà cung cấp / người bán nếu có")
    tenant_name: Optional[str] = Field(None, description="Bên thuê kho trên Hợp đồng thuê kho, không đoán nếu không có")
    lessor_name: Optional[str] = Field(None, description="Bên cho thuê kho (thường là U&I)")
    valid_from: Optional[str] = Field(None, description="Ngày bắt đầu hiệu lực hợp đồng YYYY-MM-DD")
    valid_until: Optional[str] = Field(None, description="Ngày hết hiệu lực hợp đồng YYYY-MM-DD")
    warehouse_name: Optional[str] = Field(None, description="Tên kho ngoại quan hoặc địa điểm lưu kho")
    port_of_discharge: Optional[str] = Field(None, description="Cảng dỡ hàng (Port of Discharge / Cảng đích trên BL, AN, Tờ khai)")
    vessel_voyage: Optional[str] = Field(None, description="Tên tàu / Số chuyến bay")
    eta: Optional[str] = Field(None, description="Thời gian hàng đến (Arrival Date / ETA trên AN, Tờ khai) định dạng YYYY-MM-DD")
    commodity_description: Optional[str] = Field(None, description="Tên hàng / Chủng loại mô tả chung hàng hóa")
    container_numbers: List[str] = Field(default_factory=list, description="Danh sách số container")
    seal_numbers: List[str] = Field(default_factory=list, description="Danh sách số chì niêm phong (Seal)")
    total_gross_weight_kg: Optional[float] = Field(None, description="Tổng trọng lượng Gross (kg). Chú ý: trên VNACCS '11.463' KGM là số 11463.0 kg, không được trích xuất thành 11.463")
    total_net_weight_kg: Optional[float] = Field(None, description="Tổng trọng lượng Net (kg)")
    measurement_cbm: Optional[float] = Field(None, description="Thể tích hàng hóa (CBM / m³)")
    total_packages: Optional[int] = Field(None, description="Tổng số kiện hàng. Chú ý: trên VNACCS '2.620' CT là số nguyên 2620, không được trích xuất thành 2")
    package_unit: Optional[str] = Field(None, description="Đơn vị đóng gói: CARTONS, PALLETS, BOXES, KIEN...")
    total_invoice_value: Optional[float] = Field(None, description="Tổng trị giá hóa đơn / hợp đồng SC / tờ khai. Chú ý: trên tờ khai VNACCS '16.637' USD là số 16637.0, không được trích xuất thành 16.637")
    currency: Optional[str] = Field(None, description="Đồng tiền")
    incoterms: Optional[str] = Field(None, description="Điều kiện giao hàng (CIF, FOB, EXW...)")
    contract_number_ref: Optional[str] = Field(None, description="Số hợp đồng thuê kho tham chiếu trên Tờ khai hải quan")
    invoice_number_ref: Optional[str] = Field(None, description="Số Invoice tham chiếu trên SC, Packing List, Tờ khai")
    po_numbers: List[str] = Field(default_factory=list, description="Danh sách số PO (Purchase Order) trên BL, SC, Invoice, Packing List")
    items: List[GeminiLineItemExtraction] = Field(default_factory=list, description="Danh sách các dòng hàng (SKUs)")


class ReconciledDiscrepancy(BaseModel):
    rule_code: str = Field(description="Mã quy tắc vi phạm (VAL-QTY-001, VAL-PRC-001, VAL-HS-002, VAL-CNT-001, v.v.)")
    severity: str = Field(description="Mức độ nghiêm trọng: ERROR | WARNING")
    field_name: str = Field(description="Tên trường sai lệch (Số lượng SKU, Đơn giá, Mã HS, Số container, v.v.)")
    description_vi: str = Field(description="Mô tả chi tiết sai lệch bằng tiếng Việt")
    source_doc_a: Optional[str] = Field(None, description="Tên chứng từ thứ nhất")
    value_a: Optional[str] = Field(None, description="Giá trị trên chứng từ thứ nhất")
    source_doc_b: Optional[str] = Field(None, description="Tên chứng từ thứ hai")
    value_b: Optional[str] = Field(None, description="Giá trị trên chứng từ thứ hai")


class PerDocumentExtraction(BaseModel):
    document_id: Optional[str] = Field(None, description="Mã định danh chứng từ hoặc tên tệp")
    document_type_detected: str = Field(description="Loại chứng từ: CUSTOMS_DECLARATION | COMMERCIAL_INVOICE | PACKING_LIST | BILL_OF_LADING | ARRIVAL_NOTICE | SALE_CONTRACT | PURCHASE_ORDER | CERT_OF_ORIGIN | WAREHOUSE_CONTRACT | OTHER")
    document_number: Optional[str] = Field(None, description="Số chứng từ")
    issue_date: Optional[str] = Field(None, description="Ngày phát hành (YYYY-MM-DD)")
    shipper_exporter: Optional[str] = Field(None, description="Người gửi hàng / Người xuất khẩu / Người bán")
    consignee_importer: Optional[str] = Field(None, description="Người nhận hàng cuối cùng / Consignee")
    buyer_name: Optional[str] = Field(None, description="Người mua hàng (Buyer) trên SC")
    cargo_owner_name: Optional[str] = Field(None, description="Chủ hàng / Người ủy thác")
    supplier_name: Optional[str] = Field(None, description="Tên nhà cung cấp / người bán nếu có")
    tenant_name: Optional[str] = Field(None, description="Bên thuê kho, không đoán nếu không có")
    lessor_name: Optional[str] = Field(None, description="Bên cho thuê kho")
    valid_from: Optional[str] = Field(None, description="Ngày bắt đầu hiệu lực hợp đồng YYYY-MM-DD")
    valid_until: Optional[str] = Field(None, description="Ngày hết hiệu lực hợp đồng YYYY-MM-DD")
    warehouse_name: Optional[str] = Field(None, description="Tên kho ngoại quan")
    port_of_discharge: Optional[str] = Field(None, description="Cảng dỡ hàng (Port of Discharge)")
    vessel_voyage: Optional[str] = Field(None, description="Tên tàu / Chuyến bay")
    eta: Optional[str] = Field(None, description="Thời gian hàng đến (YYYY-MM-DD)")
    commodity_description: Optional[str] = Field(None, description="Chủng loại / mô tả chung hàng hóa")
    container_numbers: List[str] = Field(default_factory=list, description="Danh sách số container")
    seal_numbers: List[str] = Field(default_factory=list, description="Danh sách số chì")
    total_gross_weight_kg: Optional[float] = Field(None, description="Tổng trọng lượng Gross (kg)")
    total_net_weight_kg: Optional[float] = Field(None, description="Tổng trọng lượng Net (kg)")
    measurement_cbm: Optional[float] = Field(None, description="Thể tích hàng hóa (CBM / m³)")
    total_packages: Optional[int] = Field(None, description="Tổng số kiện")
    package_unit: Optional[str] = Field(None, description="Đơn vị đóng gói")
    total_invoice_value: Optional[float] = Field(None, description="Tổng trị giá hóa đơn")
    currency: Optional[str] = Field(None, description="Loại tiền tệ")
    incoterms: Optional[str] = Field(None, description="Điều kiện Incoterms")
    contract_number_ref: Optional[str] = Field(None, description="Số hợp đồng thuê kho tham chiếu trên Tờ khai")
    invoice_number_ref: Optional[str] = Field(None, description="Số Invoice tham chiếu trên SC, PL, Tờ khai")
    po_numbers: List[str] = Field(default_factory=list, description="Danh sách số PO")
    items: List[GeminiLineItemExtraction] = Field(default_factory=list, description="Danh sách dòng hàng SKU của chứng từ")


class BatchShipmentReconciliationResult(BaseModel):
    shipment_code: Optional[str] = Field(None, description="Mã lô hàng nếu có")
    customs_declaration_no: Optional[str] = Field(None, description="Số tờ khai hải quan")
    overall_validity: str = Field(description="Đánh giá tổng thể tính hợp lệ: VALID | INVALID | WARNING")
    validity_reason: str = Field(description="Giải thích tổng quan lý do ĐẠT hoặc KHÔNG ĐẠT bằng tiếng Việt")
    discrepancies: List[ReconciledDiscrepancy] = Field(default_factory=list, description="Danh sách các điểm sai lệch giữa các chứng từ")
    documents: List[PerDocumentExtraction] = Field(default_factory=list, description="Dữ liệu trích xuất chi tiết theo từng chứng từ")


# --- API Models ---
class ExtractedLineItemResponse(BaseModel):
    id: str
    item_index: int
    sku: Optional[str]
    part_number: Optional[str]
    description_vi: str
    hs_code: Optional[str]
    quantity: Optional[float]
    uom: Optional[str]
    unit_price: Optional[float]
    total_amount: Optional[float]
    currency: Optional[str]
    gross_weight_kg: Optional[float]
    net_weight_kg: Optional[float]
    po_reference: Optional[str]
    page_number: Optional[int]
    raw_line_text: Optional[str] = None
    bounding_box_json: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ExtractedLineItemUpdate(BaseModel):
    sku: Optional[str] = None
    part_number: Optional[str] = None
    description_vi: Optional[str] = None
    hs_code: Optional[str] = None
    quantity: Optional[float] = None
    uom: Optional[str] = None
    unit_price: Optional[float] = None
    total_amount: Optional[float] = None
    currency: Optional[str] = None
    gross_weight_kg: Optional[float] = None
    net_weight_kg: Optional[float] = None
    po_reference: Optional[str] = None
    reason: Optional[str] = "Chỉnh sửa thủ công dữ liệu trích xuất"


class DocumentExtractionResponse(BaseModel):
    id: str
    document_id: str
    status: str
    model_name: str
    confidence_score: Optional[float]
    error_message: Optional[str]
    extracted_header_json: Optional[str] = None
    extracted_at: datetime
    version: int
    prompt_tokens: Optional[int] = None
    candidate_tokens: Optional[int] = None
    line_items: List[ExtractedLineItemResponse] = []

    model_config = ConfigDict(from_attributes=True)
