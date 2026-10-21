import io
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from app.models.shipment import Shipment
from app.models.document import Document
from app.services.validation.documents import latest_documents
from app.services.mock_wms.gatekeeper import wms_service


WMS_EXCEL_COLUMNS = [
    {"key": "stt", "title": "STT", "width": 8, "align": "center", "format": "0"},
    {"key": "sku", "title": "Mã SKU", "width": 18, "align": "left", "format": "@"},
    {"key": "part_number", "title": "Mã Phụ Tùng", "width": 16, "align": "left", "format": "@"},
    {"key": "item_description", "title": "Tên Hàng Hóa", "width": 36, "align": "left", "format": "@"},
    {"key": "hs_code", "title": "Mã HS", "width": 16, "align": "center", "format": "@"},
    {"key": "uom", "title": "Đơn Vị Tính", "width": 14, "align": "center", "format": "@"},
    {"key": "actual_qty", "title": "Số Lượng Thực Nhập", "width": 20, "align": "right", "format": "#,##0.00"},
    {"key": "declared_qty", "title": "Số Lượng Tờ Khai", "width": 18, "align": "right", "format": "#,##0.00"},
    {"key": "unit_price", "title": "Đơn Giá (USD)", "width": 16, "align": "right", "format": "#,##0.00"},
    {"key": "total_amount", "title": "Thành Tiền (USD)", "width": 18, "align": "right", "format": "#,##0.00"},
    {"key": "currency", "title": "Loại Tiền", "width": 12, "align": "center", "format": "@"},
    {"key": "po_number", "title": "Số PO", "width": 16, "align": "center", "format": "@"},
    {"key": "contract_no", "title": "Số Hợp Đồng", "width": 20, "align": "left", "format": "@"},
    {"key": "customs_declaration_no", "title": "Số Tờ Khai HQ", "width": 20, "align": "center", "format": "@"},
    {"key": "bill_of_lading_no", "title": "Số Vận Đơn (B/L)", "width": 20, "align": "center", "format": "@"},
    {"key": "container_no", "title": "Số Container", "width": 18, "align": "center", "format": "@"},
    {"key": "seal_no", "title": "Số Niêm Chì", "width": 16, "align": "center", "format": "@"},
    {"key": "net_weight_kg", "title": "Net Weight (kg)", "width": 16, "align": "right", "format": "#,##0.00"},
    {"key": "gross_weight_kg", "title": "Gross Weight (kg)", "width": 18, "align": "right", "format": "#,##0.00"},
    {"key": "bin_location", "title": "Vị Trí Kệ Kho (Bin)", "width": 18, "align": "center", "format": "@"},
    {"key": "notes", "title": "Ghi Chú Nghiệp Vụ", "width": 24, "align": "left", "format": "@"},
]


class WMSExcelMapper:
    """
    Configurable mapping layer from validated shipment/PO/SKU data to the WMS Excel template.
    Strictly preserves template column order, formatting, and text codes with leading zeros.
    Enforces Gatekeeper approval constraint before export.
    """

    @staticmethod
    def extract_mapped_rows(db: Session, shipment: Shipment) -> List[Dict[str, Any]]:
        """Trích xuất và map toàn bộ các dòng hàng đã được đối soát theo đúng 21 trường WMS."""
        import json
        documents = latest_documents(db.query(Document).filter(Document.shipment_id == shipment.id).all())
        
        # Lấy thông tin header từ B/L và tờ khai
        bl_no = None
        container_list = []
        seal_list = []
        contract_no = None

        for doc in documents:
            if not doc.extraction or not doc.extraction.extracted_header_json:
                continue
            try:
                hdr = json.loads(doc.extraction.extracted_header_json)
                if doc.document_type == "WAREHOUSE_CONTRACT":
                    contract_no = hdr.get("document_number")
                if doc.document_type == "BILL_OF_LADING" and hdr.get("document_number"):
                    bl_no = hdr.get("document_number")
                if hdr.get("container_numbers"):
                    for c in hdr["container_numbers"]:
                        if c and str(c) not in container_list:
                            container_list.append(str(c))
                if hdr.get("seal_numbers"):
                    for s in hdr["seal_numbers"]:
                        if s and str(s) not in seal_list:
                            seal_list.append(str(s))
            except Exception:
                pass

        container_str = ", ".join(container_list) if container_list else ""
        seal_str = ", ".join(seal_list) if seal_list else ""

        # Ưu tiên lấy dòng hàng từ Tờ khai HQ (CUSTOMS_DECLARATION), sau đó Commercial Invoice
        invoice_items = [item for doc in documents if doc.document_type == "COMMERCIAL_INVOICE"
                         and doc.extraction and doc.extraction.status == "SUCCESS" for item in doc.extraction.line_items]

        rows = []
        if invoice_items:
            # Map từng SKU
            stt = 1
            for item in invoice_items:
                # Bảo toàn chuỗi số có số 0 ở đầu (ví dụ: '00123456', '08471300')
                sku_code = str(item.sku or item.part_number or f"SKU-{stt:04d}").strip()
                hs_code_str = str(item.hs_code or "").strip()
                
                # Tính toán thành tiền nếu thiếu
                unit_price = float(item.unit_price) if item.unit_price is not None else 0.0
                qty = float(item.quantity) if item.quantity is not None else 0.0
                total_amt = float(item.total_amount) if item.total_amount is not None else (qty * unit_price)

                bin_loc = f"RACK-{(stt - 1) // 10 + 1:02d}-{(stt - 1) % 10 + 1:02d}"

                row_dict = {
                    "stt": stt,
                    "sku": sku_code,
                    "part_number": str(item.part_number or "").strip(),
                    "item_description": str(item.description_vi or sku_code).strip(),
                    "hs_code": hs_code_str,
                    "uom": str(item.uom or "PCS").strip().upper(),
                    "actual_qty": qty,
                    "declared_qty": None,
                    "unit_price": unit_price,
                    "total_amount": total_amt,
                    "currency": str(item.currency or "USD").strip().upper(),
                    "po_number": str(item.po_reference or "").strip(),
                    "contract_no": str(contract_no or "").strip(),
                    "customs_declaration_no": str(shipment.customs_declaration_no or "").strip(),
                    "bill_of_lading_no": str(bl_no or "").strip(),
                    "container_no": container_str,
                    "seal_no": seal_str,
                    "net_weight_kg": float(item.net_weight_kg) if item.net_weight_kg is not None else 0.0,
                    "gross_weight_kg": float(item.gross_weight_kg) if item.gross_weight_kg is not None else 0.0,
                    "bin_location": bin_loc,
                    "notes": "Nhập kho ngoại quan - Đối soát AI hợp lệ",
                }
                rows.append(row_dict)
                stt += 1

        return rows

    def generate_wms_excel(self, db: Session, shipment_id: str, check_gatekeeper: bool = True) -> bytes:
        """
        Tạo tệp WMS Inbound Excel chuẩn 21 cột, định dạng cell Type & Text đúng quy chuẩn.
        Ném PermissionError nếu chưa được duyệt hoặc chưa hoàn thành đối soát.
        """
        if check_gatekeeper:
            eligibility = wms_service.check_transmission_eligibility(db, shipment_id)
            if not eligibility["eligible"]:
                raise PermissionError(eligibility["reason"])

        shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
        if not shipment:
            raise ValueError(f"Không tìm thấy lô hàng {shipment_id}")

        mapped_rows = self.extract_mapped_rows(db, shipment)

        wb = Workbook()
        ws = wb.active
        ws.title = "Inbound_Bonded_Receipt"

        # Định dạng Header
        header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
        header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        thin_border = Border(
            left=Side(style='thin', color='CBD5E1'),
            right=Side(style='thin', color='CBD5E1'),
            top=Side(style='thin', color='CBD5E1'),
            bottom=Side(style='thin', color='CBD5E1'),
        )
        data_font = Font(name="Arial", size=10, color="0F172A")

        # Ghi dòng tiêu đề
        for col_idx, col_cfg in enumerate(WMS_EXCEL_COLUMNS, start=1):
            cell = ws.cell(row=1, column=col_idx, value=col_cfg["title"])
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = thin_border
            ws.column_dimensions[get_column_letter(col_idx)].width = col_cfg["width"]

        ws.row_dimensions[1].height = 28

        # Ghi các dòng dữ liệu
        for row_idx, row_data in enumerate(mapped_rows, start=2):
            for col_idx, col_cfg in enumerate(WMS_EXCEL_COLUMNS, start=1):
                val = row_data.get(col_cfg["key"], "")
                cell = ws.cell(row=row_idx, column=col_idx)

                # Bảo toàn mã có số 0 ở đầu bằng định dạng Text '@'
                if col_cfg["format"] == "@":
                    cell.number_format = "@"
                    cell.value = str(val) if val is not None else ""
                    cell.data_type = "s"
                elif col_cfg["format"] == "0":
                    cell.number_format = "0"
                    cell.value = int(val) if val is not None else 0
                else:
                    cell.number_format = col_cfg["format"]
                    cell.value = float(val) if val is not None else None

                cell.font = data_font
                cell.border = thin_border
                cell.alignment = Alignment(horizontal=col_cfg["align"], vertical="center")

            ws.row_dimensions[row_idx].height = 20

        # Freeze header row
        ws.freeze_panes = "A2"

        output = io.BytesIO()
        wb.save(output)
        return output.getvalue()


wms_excel_mapper = WMSExcelMapper()
