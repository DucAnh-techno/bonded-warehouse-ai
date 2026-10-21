from conftest import complete_demo_fixture
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.shipment import Shipment
from app.models.document import Document
from app.models.extraction import DocumentExtraction, ExtractedLineItem
from app.models.validation import Discrepancy, ValidationRuleSetting


def test_validation_rule_config_api(client: TestClient):
    """Kiểm tra API cấu hình quy tắc và dung sai."""
    res = client.get("/api/v1/validations/rules/config")
    assert res.status_code == 200
    rules = res.json()
    assert len(rules) >= 10
    
    # Tìm quy tắc VAL-QTY-001
    qty_rule = next(r for r in rules if r["rule_code"] == "VAL-QTY-001")
    assert qty_rule["severity"] == "ERROR"
    assert qty_rule["enabled"] is True

    # Cập nhật dung sai hoặc bật tắt
    update_res = client.put(
        "/api/v1/validations/rules/config/VAL-WGT-002",
        json={"tolerance": 1.2, "enabled": True}
    )
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["tolerance"] == 1.2


def test_get_reconciliation_matrix_loads_saved_data(client: TestClient, test_db: Session):
    """Kiểm tra GET /validations/reconcile/{shipment_id} tải lại kết quả đối soát đã lưu mà không cần gọi AI."""
    shipment = Shipment(
        shipment_code="SHP-TEST-LOAD-SAVED",
        direction="INBOUND",
        status="VALIDATED"
    )
    test_db.add(shipment)
    test_db.commit()

    # Gọi GET endpoint
    res = client.get(f"/api/v1/validations/reconcile/{shipment.id}")
    assert res.status_code == 200
    data = res.json()
    assert data["shipment_id"] == shipment.id
    assert data["shipment_code"] == "SHP-TEST-LOAD-SAVED"
    assert "sku_matrix" in data
    assert "discrepancies" in data



def test_completion_criteria_edit_sku_quantity_detects_mismatch_and_blocks_approval(
    client: TestClient, test_db: Session
):
    """
    ĐIỀU KIỆN HOÀN THÀNH GIAI ĐOẠN 4:
    Cố ý sửa số lượng một SKU giữa hai chứng từ;
    hệ thống phát hiện sai lệch và không cho phê duyệt.
    """
    # 1. Tạo lô hàng mẫu có đủ 4 loại chứng từ cốt lõi
    shipment = Shipment(
        shipment_code="SHP-TEST-CRITERIA-01",
        customs_declaration_no="105888888880",
        direction="INBOUND",
        status="DRAFT"
    )
    test_db.add(shipment)
    test_db.commit()

    # Chứng từ 1: Tờ khai HQ
    doc_dec = Document(
        shipment_id=shipment.id,
        original_filename="To_khai_HQ.pdf",
        storage_path="mock/dec.pdf",
        mime_type="application/pdf",
        sha256_hash="hash_dec",
        file_size_bytes=1000,
        document_type="CUSTOMS_DECLARATION"
    )
    # Chứng từ 2: Hóa đơn thương mại
    doc_ci = Document(
        shipment_id=shipment.id,
        original_filename="Invoice.pdf",
        storage_path="mock/ci.pdf",
        mime_type="application/pdf",
        sha256_hash="hash_ci",
        file_size_bytes=1000,
        document_type="COMMERCIAL_INVOICE"
    )
    # Chứng từ 3: Packing List
    doc_pl = Document(
        shipment_id=shipment.id,
        original_filename="PackingList.pdf",
        storage_path="mock/pl.pdf",
        mime_type="application/pdf",
        sha256_hash="hash_pl",
        file_size_bytes=1000,
        document_type="PACKING_LIST"
    )
    # Chứng từ 4: Bill of Lading
    doc_bl = Document(
        shipment_id=shipment.id,
        original_filename="BL.pdf",
        storage_path="mock/bl.pdf",
        mime_type="application/pdf",
        sha256_hash="hash_bl",
        file_size_bytes=1000,
        document_type="BILL_OF_LADING"
    )
    test_db.add_all([doc_dec, doc_ci, doc_pl, doc_bl])
    test_db.commit()

    # Thêm extractions cho từng chứng từ, ban đầu KHỚP NHAU (Quantity = 500)
    # Header chung cho tờ khai và B/L
    header_json = json.dumps({
        "container_numbers": ["TGHU1234567"],
        "total_gross_weight_kg": 1000.0,
        "total_net_weight_kg": 900.0,
        "currency": "USD",
        "incoterms": "CIF"
    })

    ext_dec = DocumentExtraction(document_id=doc_dec.id, status="SUCCESS", model_name="gemini-2.5-flash", raw_response_json="{}", extracted_header_json=header_json)
    ext_ci = DocumentExtraction(document_id=doc_ci.id, status="SUCCESS", model_name="gemini-2.5-flash", raw_response_json="{}", extracted_header_json=header_json)
    ext_pl = DocumentExtraction(document_id=doc_pl.id, status="SUCCESS", model_name="gemini-2.5-flash", raw_response_json="{}", extracted_header_json=header_json)
    ext_bl = DocumentExtraction(document_id=doc_bl.id, status="SUCCESS", model_name="gemini-2.5-flash", raw_response_json="{}", extracted_header_json=header_json)
    test_db.add_all([ext_dec, ext_ci, ext_pl, ext_bl])
    test_db.commit()

    # Dòng hàng SKU trên Tờ khai, Invoice, PL ban đầu đều là 500.0
    item_dec = ExtractedLineItem(
        extraction_id=ext_dec.id,
        item_index=1,
        sku="SKU-MICROCHIP-A1",
        description_vi="Vi mạch vi xử lý A1",
        hs_code="8542.31.00",
        quantity=500.0,
        uom="Chiếc",
        unit_price=10.0,
        total_amount=5000.0
    )
    item_ci = ExtractedLineItem(
        extraction_id=ext_ci.id,
        item_index=1,
        sku="SKU-MICROCHIP-A1",
        description_vi="Vi mạch vi xử lý A1",
        hs_code="8542.31.00",
        quantity=500.0,
        uom="Chiếc",
        unit_price=10.0,
        total_amount=5000.0
    )
    item_pl = ExtractedLineItem(
        extraction_id=ext_pl.id,
        item_index=1,
        sku="SKU-MICROCHIP-A1",
        description_vi="Vi mạch vi xử lý A1",
        hs_code="8542.31.00",
        quantity=500.0,
        uom="Chiếc"
    )
    test_db.add_all([item_dec, item_ci, item_pl])
    test_db.commit()

    complete_demo_fixture(test_db, shipment)
    # Chạy đối soát lần 1: Dữ liệu hoàn toàn khớp
    recon_res = client.post(f"/api/v1/validations/reconcile/{shipment.id}")
    assert recon_res.status_code == 200
    recon_data = recon_res.json()
    assert recon_data["error_count"] == 0
    assert recon_data["validation_status"] == "VALIDATED"
    assert len(recon_data["sku_matrix"]) == 1
    assert recon_data["sku_matrix"][0]["is_matched"] is True

    # 2. CỐ Ý SỬA SỐ LƯỢNG SKU TRÊN HÓA ĐƠN THƯƠNG MẠI (CI) TỪ 500.0 THÀNH 450.0
    edit_res = client.patch(
        f"/api/v1/extractions/items/{item_ci.id}",
        json={"quantity": 450.0, "reason": "Cố ý chỉnh sửa số lượng để kiểm tra quy tắc đối soát"}
    )
    assert edit_res.status_code == 200
    edited_item = edit_res.json()
    assert edited_item["quantity"] == 450.0

    # 3. KIỂM TRA HỆ THỐNG ĐÃ TỰ ĐỘNG PHÁT HIỆN SAI LỆCH QUA DYNAMIC REVALIDATION
    test_db.refresh(shipment)
    assert shipment.status == "DISCREPANT"

    # Lấy danh sách bất đồng bộ của lô hàng
    disc_res = client.get(f"/api/v1/validations/discrepancies/{shipment.id}")
    assert disc_res.status_code == 200
    discrepancies = disc_res.json()

    qty_discrepancy = next((d for d in discrepancies if d["rule_code"] == "VAL-QTY-001"), None)
    assert qty_discrepancy is not None, "Hệ thống phải phát hiện bất đồng bộ số lượng VAL-QTY-001"
    assert qty_discrepancy["severity"] == "ERROR"
    assert qty_discrepancy["status"] == "OPEN"

    # 4. KIỂM TRA HỆ THỐNG CHẶN PHÊ DUYỆT (BLOCK APPROVAL)
    approval_res = client.post(
        f"/api/v1/validations/shipment/{shipment.id}/approve",
        json={"approved_by": "supervisor_01", "notes": "Thử phê duyệt khi đang có lỗi"}
    )
    assert approval_res.status_code == 200
    approval_data = approval_res.json()
    assert approval_data["success"] is False
    assert approval_data["is_blocked"] is True
    assert "Không thể phê duyệt" in approval_data["message_vi"]
    assert len(approval_data["blocking_reasons"]) > 0

    # Đồng thời thử gọi cổng WMS Gatekeeper trực tiếp
    wms_res = client.post(
        f"/api/v1/wms/approve/{shipment.id}",
        json={"approved_by": "supervisor_01", "approval_notes": "Thử duyệt WMS"}
    )
    assert wms_res.status_code == 400

    # 5. GIẢI QUYẾT BẤT ĐỒNG BỘ BẰNG GHI ĐÈ / CHẤP THUẬN NGHIỆP VỤ (HITL)
    resolve_res = client.post(
        f"/api/v1/validations/discrepancies/{qty_discrepancy['id']}/resolve",
        json={
            "action": "ACCEPTED",
            "reason": "Cán bộ kiểm tra xác nhận nhà cung cấp giao thiếu 50 chiếc theo biên bản giải trình số 12/BB-HQ",
            "resolved_by": "customs_officer"
        }
    )
    assert resolve_res.status_code == 200

    # Tái đối soát lại sau khi lỗi đã được giải quyết
    test_db.refresh(shipment)
    # Lấy danh sách discrepancies sau giải quyết
    open_errors = [
        d for d in client.get(f"/api/v1/validations/discrepancies/{shipment.id}").json()
        if d["severity"] == "ERROR" and d["status"] == "OPEN"
    ]
    # Sửa nốt math total nếu có lệch line total
    for d in open_errors:
        client.post(
            f"/api/v1/validations/discrepancies/{d['id']}/resolve",
            json={"action": "ACCEPTED", "reason": "Chấp thuận điều chỉnh giá trị", "resolved_by": "customs_officer"}
        )

    # Acceptance alone cannot waive an actual mismatch; correct the source value.
    blocked = client.post(f"/api/v1/validations/shipment/{shipment.id}/approve", json={"approved_by":"reviewer"})
    assert blocked.json()["success"] is False
    assert client.patch(f"/api/v1/extractions/items/{item_ci.id}", json={"quantity":500, "reason":"Correct OCR"}).status_code == 200

    # 6. PHÊ DUYỆT THÀNH CÔNG SAU KHI TẤT CẢ LỖI ĐƯỢC XỬ LÝ
    final_approval = client.post(
        f"/api/v1/validations/shipment/{shipment.id}/approve",
        json={"approved_by": "supervisor_01", "notes": "Hồ sơ đã được kiểm tra và giải trình đầy đủ"}
    )
    assert final_approval.status_code == 200
    final_data = final_approval.json()
    assert final_data["success"] is True
    assert final_data["is_blocked"] is False
    assert final_data["approval_status"] == "APPROVED"
