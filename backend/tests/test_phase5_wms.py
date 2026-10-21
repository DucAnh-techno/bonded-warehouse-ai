from conftest import complete_demo_fixture
import io
import json
import pytest
from openpyxl import load_workbook
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.shipment import Shipment
from app.models.document import Document
from app.models.extraction import DocumentExtraction, ExtractedLineItem
from app.models.validation import Discrepancy, WMSTransmission
from app.models.wms import WMSReceipt, WMSReceiptItem
from app.services.export.excel_mapper import wms_excel_mapper, WMS_EXCEL_COLUMNS
from app.services.mock_wms.gatekeeper import wms_service
from app.schemas.wms import WMSInboundReceiptPayload, WMSLineItemPayload


import uuid

def _create_sample_valid_shipment(test_db: Session) -> Shipment:
    """Tạo một lô hàng hợp lệ hoàn chỉnh với chứng từ và SKU có mã bảo toàn số 0 ở đầu."""
    suffix = uuid.uuid4().hex[:6].upper()
    ship_code = f"SHP-WMS-{suffix}"
    dec_no = f"0100{suffix}"

    shipment = Shipment(
        shipment_code=ship_code,
        customs_declaration_no=dec_no,
        warehouse_type="BONDED",
        direction="INBOUND",
        status="VALIDATED",
        approval_status="PENDING"
    )
    test_db.add(shipment)
    test_db.flush()

    # Document 1: Tờ khai hải quan
    doc_dec = Document(
        shipment_id=shipment.id,
        document_type="CUSTOMS_DECLARATION",
        original_filename=f"To_Khai_HQ_{dec_no}.pdf",
        storage_path=f"uploads/test_dec_{suffix}.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        sha256_hash=f"hash_dec_{suffix}"
    )
    test_db.add(doc_dec)
    test_db.flush()

    ext_dec = DocumentExtraction(
        document_id=doc_dec.id,
        status="SUCCESS",
        model_name="gemini-2.5-flash",
        raw_response_json="{}",
        extracted_header_json=json.dumps({
            "document_number": dec_no,
            "shipper": "GLOBAL LOGISTICS CORP",
            "consignee": "KHO NGOAI QUAN VIETNAM",
            "vessel_voyage": "WAN HAI 312 V.021",
            "container_numbers": ["TCNU1234567"],
            "seal_numbers": ["SEAL00987"],
            "total_gross_weight_kg": 1500.0,
            "total_packages": 100,
            "currency": "USD"
        })
    )
    test_db.add(ext_dec)
    test_db.flush()

    # SKU 1: Mã SKU có số 0 ở đầu ("004521"), HS Code ("08471300")
    item1 = ExtractedLineItem(
        extraction_id=ext_dec.id,
        item_index=1,
        sku="004521",
        part_number="00PN-99",
        description_vi="Bo mach chu dien tu VN-01",
        hs_code="08471300",
        quantity=500.0,
        uom="PCS",
        unit_price=12.50,
        total_amount=6250.0,
        currency="USD",
        gross_weight_kg=750.0,
        net_weight_kg=700.0,
        po_reference="PO-2026-001"
    )
    # SKU 2: Mã SKU thông thường
    item2 = ExtractedLineItem(
        extraction_id=ext_dec.id,
        item_index=2,
        sku="SKU-8899",
        part_number="PN-88",
        description_vi="Man hinh hien thi LCD 14 inch",
        hs_code="85285200",
        quantity=200.0,
        uom="PCS",
        unit_price=45.00,
        total_amount=9000.0,
        currency="USD",
        gross_weight_kg=750.0,
        net_weight_kg=720.0,
        po_reference="PO-2026-002"
    )
    test_db.add_all([item1, item2])
    test_db.commit()
    test_db.refresh(shipment)
    complete_demo_fixture(test_db, shipment)
    return shipment


def test_excel_mapping_21_columns_and_leading_zeros(test_db: Session):
    """
    Test 1: Kiểm tra mapping đủ 21 cột và bảo toàn số 0 ở đầu trong Excel WMS.
    Bảo toàn số 0 cho: Mã SKU ('004521'), Mã HS ('08471300'), Số tờ khai ('010023456789').
    """
    shipment = _create_sample_valid_shipment(test_db)
    # Phê duyệt để mở khóa xuất excel
    shipment.approval_status = "APPROVED"
    shipment.approved_by = "GiamSatKho"
    test_db.commit()

    # Trích xuất các dòng mapped
    rows = wms_excel_mapper.extract_mapped_rows(test_db, shipment)
    assert len(rows) == 2

    row1 = rows[0]
    assert row1["sku"] == "004521"
    assert row1["part_number"] == "00PN-99"
    assert row1["hs_code"] == "08471300"
    assert row1["customs_declaration_no"] == shipment.customs_declaration_no
    assert row1["actual_qty"] == 500.0
    assert row1["unit_price"] == 12.50
    assert row1["total_amount"] == 6250.0

    # Tạo tệp Excel binary và đọc lại bằng openpyxl
    excel_bytes = wms_excel_mapper.generate_wms_excel(test_db, shipment.id)
    wb = load_workbook(io.BytesIO(excel_bytes))
    ws = wb.active
    assert ws.title == "Inbound_Bonded_Receipt"

    # Kiểm tra số lượng cột tiêu đề (21 cột)
    assert len(WMS_EXCEL_COLUMNS) == 21
    for col_idx, col_cfg in enumerate(WMS_EXCEL_COLUMNS, start=1):
        cell_val = ws.cell(row=1, column=col_idx).value
        assert cell_val == col_cfg["title"]

    # Kiểm tra dòng dữ liệu 1 (Dòng 2 trong Excel)
    sku_cell = ws.cell(row=2, column=2)  # Cột B: Mã SKU
    assert sku_cell.value == "004521"
    assert sku_cell.number_format == "@"

    hs_cell = ws.cell(row=2, column=5)   # Cột E: Mã HS
    assert hs_cell.value == "08471300"
    assert hs_cell.number_format == "@"

    dec_cell = ws.cell(row=2, column=14) # Cột N: Số Tờ Khai HQ
    assert dec_cell.value == shipment.customs_declaration_no
    assert dec_cell.number_format == "@"

    qty_cell = ws.cell(row=2, column=7)  # Cột G: Số Lượng Thực Nhập
    assert qty_cell.value == 500.0
    assert qty_cell.number_format == "#,##0.00"


def test_gatekeeper_blocks_unvalidated_and_unapproved(client: TestClient, test_db: Session):
    """
    Test 2: Kiểm tra Gatekeeper chặn xuất Excel và truyền WMS:
    1. Khi lô hàng chưa được phê duyệt (status 403).
    2. Khi lô hàng còn lỗi bất đồng bộ cấp ERROR (status 403).
    """
    shipment = _create_sample_valid_shipment(test_db)
    
    # 1. Chưa phê duyệt (approval_status == 'PENDING') -> Bị chặn 403
    res_excel = client.get(f"/api/v1/wms/export-excel/{shipment.id}")
    assert res_excel.status_code == 403
    assert "chữ ký phê duyệt" in res_excel.json()["detail"]

    res_transmit = client.post(
        f"/api/v1/wms/transmit/{shipment.id}",
        json={"approved_by": "NguyenVanA"}
    )
    assert res_transmit.status_code == 403
    assert "chữ ký phê duyệt" in res_transmit.json()["detail"]

    # 2. Thêm một lỗi bất đồng bộ cấp ERROR -> Bị chặn kể cả khi cố phê duyệt
    disc = Discrepancy(
        shipment_id=shipment.id,
        rule_code="VAL-QTY-001",
        severity="ERROR",
        field_name="quantity",
        description_vi="Sai lệch số lượng tồn tại.",
        status="OPEN"
    )
    test_db.add(disc)
    packing = test_db.query(Document).filter_by(shipment_id=shipment.id, document_type="PACKING_LIST").one()
    packing.extraction.line_items[0].quantity += 1
    shipment.status = "DISCREPANT"
    test_db.commit()

    # Thử phê duyệt khi còn lỗi -> Bị từ chối 400
    res_approve = client.post(
        f"/api/v1/wms/approve/{shipment.id}",
        json={"approved_by": "NguyenVanA", "approval_notes": "Cố duyệt"}
    )
    assert res_approve.status_code == 400
    assert "lỗi bất đồng bộ" in res_approve.json()["detail"]

    # Gatekeeper check status báo không đủ điều kiện
    res_status = client.get(f"/api/v1/wms/status/{shipment.id}")
    assert res_status.status_code == 200
    assert res_status.json()["eligible"] is False


def test_wms_idempotency_prevents_duplicate_receipts(client: TestClient, test_db: Session):
    """
    Test 3: Kiểm tra tính Idempotent: Gửi API tạo phiếu nhập kho 2 lần liên tiếp
    với cùng mã lô hàng & số tờ khai -> Hệ thống chỉ tạo đúng 1 phiếu nhập duy nhất,
    lần thứ 2 trả về trạng thái ALREADY_RECEIVED và is_duplicate = True.
    """
    payload_dict = {
        "receipt_id": "RCPT-TEST-IDEMPOTENT-01",
        "shipment_code": "SHP-IDEMP-2026",
        "customs_declaration_no": "100998877665",
        "warehouse_type": "BONDED",
        "receipt_date": "2026-10-11",
        "shipper": "LOGISTICS SUPPLIER",
        "consignee": "BONDED WAREHOUSE",
        "total_line_items": 1,
        "line_items": [
            {
                "line_number": 1,
                "sku": "009911",
                "item_description": "Linh kien vi mach",
                "hs_code": "85423100",
                "quantity": 100.0,
                "uom": "PCS",
                "unit_price": 5.0,
                "currency": "USD"
            }
        ]
    }

    # Lần gửi 1: Tạo mới thành công
    res1 = client.post("/api/v1/wms/mock/inbound-receipts", json=payload_dict)
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["status"] == "RECEIVED"
    assert data1["is_duplicate"] is False
    assert data1["receipt_id"] == "RCPT-TEST-IDEMPOTENT-01"

    # Lần gửi 2: Trùng lặp idempotency_key -> Nhận diện duplicate
    res2 = client.post("/api/v1/wms/mock/inbound-receipts", json=payload_dict)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["status"] == "ALREADY_RECEIVED"
    assert data2["is_duplicate"] is True
    assert data2["receipt_id"] == "RCPT-TEST-IDEMPOTENT-01"

    # Kiểm tra database: Đúng 1 phiếu WMSReceipt duy nhất
    receipts_in_db = test_db.query(WMSReceipt).filter(
        WMSReceipt.idempotency_key == "SHP-IDEMP-2026:100998877665"
    ).all()
    assert len(receipts_in_db) == 1

    # Kiểm tra số lượng dòng hàng: Đúng 1 dòng SKU duy nhất, không nhân đôi
    items_in_db = test_db.query(WMSReceiptItem).filter(
        WMSReceiptItem.receipt_id == receipts_in_db[0].id
    ).all()
    assert len(items_in_db) == 1
    assert items_in_db[0].sku == "009911"


def test_simulated_failure_leaves_no_inconsistent_state(client: TestClient, test_db: Session):
    """
    Test 4: Mô phỏng lỗi kết nối WMS (503 Service Unavailable).
    Hệ thống ghi log thất bại vào WMSTransmission, nhưng không tạo phiếu nhập rác
    trong bảng WMSReceipt (đảm bảo tính toàn vẹn dữ liệu).
    """
    shipment = _create_sample_valid_shipment(test_db)
    
    # Phê duyệt hồ sơ
    approve_res = client.post(
        f"/api/v1/wms/approve/{shipment.id}",
        json={"approved_by": "GiamSatKho", "approval_notes": "Phe duyet thu nghiem loi"}
    )
    assert approve_res.status_code == 200

    # Truyền WMS với simulate_failure = True
    trans_res = client.post(
        f"/api/v1/wms/transmit/{shipment.id}",
        json={"approved_by": "GiamSatKho", "simulate_failure": True}
    )
    assert trans_res.status_code == 503
    assert "WMS_SIMULATED_FAILURE" in trans_res.json()["detail"]

    # Kiểm tra: Trong bảng WMSTransmission có ghi nhận log FAILED với HTTP 503
    trans_log = test_db.query(WMSTransmission).filter(
        WMSTransmission.shipment_id == shipment.id
    ).first()
    assert trans_log is not None
    assert trans_log.status == "FAILED"
    assert trans_log.wms_response_code == 503

    # Kiểm tra: Không có phiếu nhập kho nào được tạo trong bảng WMSReceipt
    receipt = test_db.query(WMSReceipt).filter(
        WMSReceipt.shipment_id == shipment.id
    ).first()
    assert receipt is None


def test_end_to_end_wms_flow(client: TestClient, test_db: Session):
    """
    Test 5 (Điều kiện hoàn thành):
    Hồ sơ hợp lệ tạo Excel đúng cấu trúc và gửi API tạo một phiếu nhập duy nhất.
    """
    # 1. Khởi tạo lô hàng hợp lệ
    shipment = _create_sample_valid_shipment(test_db)

    # 2. Phê duyệt lô hàng
    approve_res = client.post(
        f"/api/v1/wms/approve/{shipment.id}",
        json={"approved_by": "TruongPhongHaiQuan", "approval_notes": "Ho so hop le 100%"}
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["approval_status"] == "APPROVED"

    # 3. Tải file Excel WMS và kiểm tra cấu trúc
    excel_res = client.get(f"/api/v1/wms/export-excel/{shipment.id}")
    assert excel_res.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in excel_res.headers["content-type"]
    assert len(excel_res.content) > 0

    wb = load_workbook(io.BytesIO(excel_res.content))
    ws = wb.active
    assert ws.title == "Inbound_Bonded_Receipt"
    assert ws.max_column == 21
    assert ws.max_row == 3  # 1 header + 2 SKU rows

    # 4. Gửi API truyền vào WMS
    transmit_res = client.post(
        f"/api/v1/wms/transmit/{shipment.id}",
        json={"approved_by": "TruongPhongHaiQuan", "simulate_failure": False}
    )
    assert transmit_res.status_code == 200
    trans_data = transmit_res.json()
    assert trans_data["status"] == "TRANSMITTED"
    assert trans_data["wms_response_code"] == 200

    # 5. Kiểm tra danh sách phiếu nhập kho trong Mock WMS
    receipts_res = client.get("/api/v1/wms/mock/inbound-receipts")
    assert receipts_res.status_code == 200
    receipts = receipts_res.json()
    matching_receipts = [r for r in receipts if r["shipment_code"] == shipment.shipment_code]
    assert len(matching_receipts) == 1

    rcpt_id = matching_receipts[0]["id"]
    detail_res = client.get(f"/api/v1/wms/mock/inbound-receipts/{rcpt_id}")
    assert detail_res.status_code == 200
    rcpt_detail = detail_res.json()
    assert rcpt_detail["shipment_code"] == shipment.shipment_code
    assert rcpt_detail["customs_declaration_no"] == shipment.customs_declaration_no
    assert len(rcpt_detail["items"]) == 2

    # Kiểm tra bảo toàn số 0 trong Mock WMS
    skus_in_rcpt = [it["sku"] for it in rcpt_detail["items"]]
    assert "004521" in skus_in_rcpt
    assert "SKU-8899" in skus_in_rcpt

    # 6. Gửi truyền lại lần 2 để kiểm tra chống trùng lặp qua API truyền
    transmit_res2 = client.post(
        f"/api/v1/wms/transmit/{shipment.id}",
        json={"approved_by": "TruongPhongHaiQuan"}
    )
    assert transmit_res2.status_code == 200
    # Số lượng phiếu nhập vẫn là 1 duy nhất
    receipts_after = client.get("/api/v1/wms/mock/inbound-receipts").json()
    matching_after = [r for r in receipts_after if r["shipment_code"] == shipment.shipment_code]
    assert len(matching_after) == 1
