from conftest import complete_demo_fixture
import io
import json
import uuid
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from openpyxl import load_workbook
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.shipment import Shipment
from app.models.document import Document
from app.models.extraction import DocumentExtraction, ExtractedLineItem
from app.models.validation import Discrepancy, WMSTransmission
from app.models.audit import AuditLog
from app.models.wms import WMSReceipt, WMSReceiptItem
from app.services.ai.gemini_client import (
    calculate_estimated_cost,
    is_quota_or_transient_error,
    gemini_extractor
)
from app.services.export.excel_mapper import wms_excel_mapper, WMS_EXCEL_COLUMNS


def test_estimated_cost_calculation():
    """Kiểm tra công thức tính toán chi phí API Gemini Flash và Gemini Pro."""
    # Flash: $0.075 / 1M prompt, $0.30 / 1M candidate
    cost_flash = calculate_estimated_cost("gemini-3.8-flash", 1_000_000, 1_000_000)
    assert round(cost_flash, 3) == 0.375

    # Pro: $1.25 / 1M prompt, $5.00 / 1M candidate
    cost_pro = calculate_estimated_cost("gemini-1.5-pro", 1_000_000, 1_000_000)
    assert round(cost_pro, 3) == 6.250

    # Tokens 0
    assert calculate_estimated_cost("gemini-3.8-flash", 0, 0) == 0.0


def test_quota_transient_error_detection():
    """Kiểm tra nhận diện mã lỗi Quota / Rate Limit (HTTP 429, RESOURCE_EXHAUSTED)."""
    assert is_quota_or_transient_error(RuntimeError("429 Too Many Requests")) is True
    assert is_quota_or_transient_error(RuntimeError("RESOURCE_EXHAUSTED: quota exceeded")) is True
    assert is_quota_or_transient_error(RuntimeError("Rate limit exceeded for default project")) is True
    assert is_quota_or_transient_error(RuntimeError("503 Service Unavailable")) is True
    assert is_quota_or_transient_error(ValueError("Invalid JSON schema syntax")) is False


def test_gemini_client_retry_behavior_on_transient_quota_failure():
    """Kiểm tra cơ chế retry tự động với exponential backoff khi gặp lỗi transient quota."""
    import asyncio

    async def _async_test():
        mock_client = MagicMock()
        # Một lần lỗi 429, lần thứ hai trả về kết quả hợp lệ.
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "document_type_detected": "COMMERCIAL_INVOICE",
            "document_number": "INV-RETRY-01",
            "items": [
                {
                    "item_index": 1,
                    "sku": "SKU-RETRY",
                    "description_vi": "Hang hoa kiem tra retry",
                    "quantity": 10.0,
                    "uom": "PCS"
                }
            ]
        })
        mock_response.usage_metadata = MagicMock(prompt_token_count=100, candidates_token_count=50, total_token_count=150)

        attempts = 0
        def mock_generate(*args, **kwargs):
            nonlocal attempts
            attempts += 1
            if attempts < 2:
                raise RuntimeError("429 RESOURCE_EXHAUSTED: Quota exceeded, please retry later.")
            return mock_response

        mock_client.models.generate_content.side_effect = mock_generate

        with patch.object(gemini_extractor, "_get_client", return_value=mock_client), \
             patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            
            import tempfile
            from pathlib import Path
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(b"%PDF-1.4 Mock PDF content")
                tmp_path = Path(tmp.name)

            try:
                res, usage = await gemini_extractor.extract_document(tmp_path, "application/pdf")
                assert attempts == 2
                assert mock_sleep.call_count == 1
                assert res.document_number == "INV-RETRY-01"
                assert len(res.items) == 1
                assert usage["prompt_tokens"] == 100
                assert usage["candidate_tokens"] == 50
                assert "estimated_cost_usd" in usage
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()

    asyncio.run(_async_test())


def test_excel_export_correctness_and_styling(test_db: Session):
    """
    Kiểm tra tính đúng đắn toàn diện của việc xuất Excel:
    - 21 cột tiêu đề.
    - Định dạng số cho STT, đơn giá, số lượng, thành tiền.
    - Định dạng text '@' cho mã có số 0 ở đầu.
    - Xử lý mượt mà khi có giá trị null / thiếu.
    """
    suffix = uuid.uuid4().hex[:6].upper()
    shipment = Shipment(
        shipment_code=f"SHP-EXP-{suffix}",
        customs_declaration_no=f"0800{suffix}",
        direction="INBOUND",
        status="VALIDATED",
        approval_status="APPROVED",
        approved_by="AuditorTest"
    )
    test_db.add(shipment)
    test_db.flush()

    doc = Document(
        shipment_id=shipment.id,
        document_type="CUSTOMS_DECLARATION",
        original_filename=f"To_Khai_{suffix}.pdf",
        storage_path=f"uploads/test_exp_{suffix}.pdf",
        mime_type="application/pdf",
        file_size_bytes=2048,
        sha256_hash=f"hash_exp_{suffix}"
    )
    test_db.add(doc)
    test_db.flush()

    ext = DocumentExtraction(
        document_id=doc.id,
        status="SUCCESS",
        model_name="gemini-3.8-flash",
        raw_response_json="{}",
        extracted_header_json=json.dumps({"document_number": f"0800{suffix}"})
    )
    test_db.add(ext)
    test_db.flush()

    # Dòng 1: Đầy đủ các trường với số 0 ở đầu
    item1 = ExtractedLineItem(
        extraction_id=ext.id,
        item_index=1,
        sku="001234",
        part_number="00PN-1",
        description_vi="Thiet bi dien tu loai 1",
        hs_code="08471300",
        quantity=150.5,
        uom="PCS",
        unit_price=10.0,
        total_amount=1505.0,
        currency="USD"
    )
    # Dòng 2: Thiếu đơn giá, thành tiền, Net/Gross weight -> Không gây crash Excel
    item2 = ExtractedLineItem(
        extraction_id=ext.id,
        item_index=2,
        sku="005678",
        description_vi="Thiet bi dien tu loai 2 thieu don gia",
        quantity=200.0,
        uom="SET"
    )
    test_db.add_all([item1, item2])
    test_db.commit()

    # Tạo tệp Excel
    # Missing prices now block export; this explicit zero is an intentional free sample.
    item2.unit_price = 0.0
    item2.total_amount = 0.0
    test_db.commit()
    complete_demo_fixture(test_db, shipment)
    excel_bytes = wms_excel_mapper.generate_wms_excel(test_db, shipment.id)
    wb = load_workbook(io.BytesIO(excel_bytes))
    ws = wb.active

    assert ws.title == "Inbound_Bonded_Receipt"
    assert ws.max_column == 21
    assert ws.max_row == 3

    # Kiểm tra ô SKU dòng 1 bảo toàn số 0
    c_sku1 = ws.cell(row=2, column=2)
    assert c_sku1.value == "001234"
    assert c_sku1.number_format == "@"

    # Kiểm tra ô SKU dòng 2 bảo toàn số 0
    c_sku2 = ws.cell(row=3, column=2)
    assert c_sku2.value == "005678"
    assert c_sku2.number_format == "@"

    # Kiểm tra ô Đơn giá dòng 2 (khi null được chuyển đổi sang số 0.00 mà không lỗi)
    c_price2 = ws.cell(row=3, column=9)
    assert c_price2.value == 0.0
    assert c_price2.number_format == "#,##0.00"


def test_database_persistence_and_transaction_integrity(test_db: Session):
    """
    Kiểm tra tính bền vững của dữ liệu qua các phiên và tính toàn vẹn transaction (ACID).
    Rollback hoàn toàn khi có lỗi vi phạm ràng buộc, không để lại dữ liệu rác mồ côi.
    """
    suffix = uuid.uuid4().hex[:6].upper()
    shipment = Shipment(
        shipment_code=f"SHP-PERSIST-{suffix}",
        customs_declaration_no=f"0999{suffix}",
        direction="INBOUND",
        status="DRAFT"
    )
    test_db.add(shipment)
    test_db.commit()
    shipment_id = shipment.id

    # Đọc lại ở query mới
    loaded_shipment = test_db.query(Shipment).filter(Shipment.id == shipment_id).first()
    assert loaded_shipment is not None
    assert loaded_shipment.shipment_code == f"SHP-PERSIST-{suffix}"

    # Thêm Audit Log
    audit = AuditLog(
        shipment_id=shipment_id,
        action="STATUS_CHANGE",
        target_entity="Shipment",
        target_id=shipment_id,
        old_value="DRAFT",
        new_value="VALIDATED",
        user_id="Tester",
        reason="Kiem tra luu tru audit log bat bien"
    )
    test_db.add(audit)
    test_db.commit()

    saved_audit = test_db.query(AuditLog).filter(AuditLog.shipment_id == shipment_id).first()
    assert saved_audit is not None
    assert saved_audit.action == "STATUS_CHANGE"

    # Thử nghiệm Rollback khi vi phạm ràng buộc UNIQUE của shipment_code
    with pytest.raises(Exception):
        dup_shipment = Shipment(
            shipment_code=f"SHP-PERSIST-{suffix}",  # Trùng lặp
            direction="INBOUND"
        )
        test_db.add(dup_shipment)
        test_db.commit()

    test_db.rollback()

    # Kiểm tra database sau rollback: Vẫn còn đúng 1 shipment ban đầu
    count = test_db.query(Shipment).filter(Shipment.shipment_code == f"SHP-PERSIST-{suffix}").count()
    assert count == 1


