from conftest import complete_demo_fixture
import pytest
from app.models.shipment import Shipment
from app.models.validation import Discrepancy
from app.services import wms_service


def test_wms_gatekeeper_blocks_when_discrepancies_exist(test_db):
    # 1. Create a shipment
    shipment = Shipment(
        shipment_code="SHP-TEST-001",
        customs_declaration_no="100234567890",
        status="DISCREPANT",
        approval_status="APPROVED"
    )
    test_db.add(shipment)
    test_db.commit()

    # 2. Add an unresolved ERROR discrepancy
    discrepancy = Discrepancy(
        shipment_id=shipment.id,
        rule_code="VAL-QTY-001",
        severity="ERROR",
        field_name="quantity",
        description_vi="Số lượng lệch giữa Invoice và Packing List",
        status="OPEN"
    )
    test_db.add(discrepancy)
    test_db.commit()

    # 3. Test eligibility
    eligibility = wms_service.check_transmission_eligibility(test_db, shipment.id)
    assert eligibility["eligible"] is False
    assert "lỗi bất đồng bộ nghiêm trọng" in eligibility["reason"]

    # 4. Attempt transmission should raise PermissionError
    with pytest.raises(PermissionError):
        wms_service.transmit_to_wms(test_db, shipment.id, approved_by="supervisor")


def test_wms_gatekeeper_blocks_when_not_approved(test_db):
    shipment = Shipment(
        shipment_code="SHP-TEST-002",
        customs_declaration_no="100234567891",
        status="VALIDATED",
        approval_status="PENDING"  # Not yet approved
    )
    test_db.add(shipment)
    test_db.commit()

    eligibility = wms_service.check_transmission_eligibility(test_db, shipment.id)
    assert eligibility["eligible"] is False
    assert "phê duyệt" in eligibility["reason"]


def test_wms_gatekeeper_unlocks_when_validated_and_approved(test_db):
    shipment = Shipment(
        shipment_code="SHP-TEST-003",
        customs_declaration_no="100234567892",
        status="VALIDATED",
        approval_status="APPROVED"
    )
    test_db.add(shipment)
    test_db.commit()

    eligibility = wms_service.check_transmission_eligibility(test_db, shipment.id)
    complete_demo_fixture(test_db, shipment)
    eligibility = wms_service.check_transmission_eligibility(test_db, shipment.id)
    assert eligibility["eligible"] is True

    # Transmission succeeds
    transmission = wms_service.transmit_to_wms(test_db, shipment.id, approved_by="supervisor_nguyen")
    assert transmission.status == "TRANSMITTED"
    assert transmission.is_blocked is False
    assert shipment.status == "TRANSMITTED"


def test_bl_transport_docs_excluded_from_sku_reconciliation(test_db):
    """
    Kiểm tra chứng từ vận tải B/L hoặc Arrival Notice chỉ chứa thông tin vận chuyển cấp container,
    không tham gia vào ma trận đối soát SKU và không gây lỗi sai lệch số lượng / mã HS giả lập.
    """
    import json
    from app.models.document import Document
    from app.models.extraction import DocumentExtraction, ExtractedLineItem
    from app.services.validation.reconciler import reconciliation_engine

    from datetime import date
    shipment = Shipment(
        shipment_code="SHP-TEST-BL-01",
        customs_declaration_no="107894526460",
        inbound_source="FOREIGN",
        entry_date=date(2026, 10, 11),
        partner_name="U&I LOGISTICS",
        notes="Bàn ghế gỗ",
        status="DRAFT"
    )
    test_db.add(shipment)
    test_db.commit()

    # Document 1: Customs Declaration with SKU-001 (100 pcs)
    doc_dec = Document(
        shipment_id=shipment.id,
        document_type="CUSTOMS_DECLARATION",
        original_filename="ToKhaiHQ.xls",
        storage_path="uploads/mock_dec.xls",
        mime_type="application/vnd.ms-excel",
        sha256_hash="hash1",
        file_size_bytes=1000
    )
    test_db.add(doc_dec)
    test_db.flush()

    ext_dec = DocumentExtraction(
        document_id=doc_dec.id,
        model_name="gemini-2.5-flash",
        status="SUCCESS",
        raw_response_json="{}",
        extracted_header_json=json.dumps({
            "document_number": "107894526460",
            "container_numbers": ["TXGU7251747"],
            "seal_numbers": ["EMCQPS9244"],
            "total_gross_weight_kg": 7515.1,
            "total_net_weight_kg": 6500.0,
            "currency": "USD"
        })
    )
    test_db.add(ext_dec)
    test_db.flush()

    test_db.add(ExtractedLineItem(
        extraction_id=ext_dec.id,
        item_index=1,
        sku="SKU-001",
        description_vi="Bàn ghế gỗ",
        hs_code="9403.60.90",
        quantity=100,
        uom="Bộ",
        unit_price=50.0,
        total_amount=5000.0
    ))

    # Document 2: Commercial Invoice with SKU-001 (100 pcs)
    doc_ci = Document(
        shipment_id=shipment.id,
        document_type="COMMERCIAL_INVOICE",
        original_filename="Invoice.pdf",
        storage_path="uploads/mock_ci.pdf",
        mime_type="application/pdf",
        sha256_hash="hash2",
        file_size_bytes=1000
    )
    test_db.add(doc_ci)
    test_db.flush()

    ext_ci = DocumentExtraction(
        document_id=doc_ci.id,
        model_name="gemini-2.5-flash",
        status="SUCCESS",
        raw_response_json="{}",
        extracted_header_json=json.dumps({
            "document_number": "INV-2026-001",
            "total_invoice_value": 5000.0,
            "currency": "USD",
            "incoterms": "CIF"
        })
    )
    test_db.add(ext_ci)
    test_db.flush()

    test_db.add(ExtractedLineItem(
        extraction_id=ext_ci.id,
        item_index=1,
        sku="SKU-001",
        description_vi="Bàn ghế gỗ",
        hs_code="9403.60.90",
        quantity=100,
        uom="Bộ",
        unit_price=50.0,
        total_amount=5000.0
    ))

    # Document 2.5: Packing List with SKU-001 (100 pcs)
    doc_pl = Document(
        shipment_id=shipment.id,
        document_type="PACKING_LIST",
        original_filename="PackingList.pdf",
        storage_path="uploads/mock_pl.pdf",
        mime_type="application/pdf",
        sha256_hash="hash25",
        file_size_bytes=1000
    )
    test_db.add(doc_pl)
    test_db.flush()

    ext_pl = DocumentExtraction(
        document_id=doc_pl.id,
        model_name="gemini-2.5-flash",
        status="SUCCESS",
        raw_response_json="{}",
        extracted_header_json=json.dumps({
            "document_number": "PL-2026-001",
            "total_packages": "222 CARTONS",
            "total_gross_weight_kg": 7515.1
        })
    )
    test_db.add(ext_pl)
    test_db.flush()

    test_db.add(ExtractedLineItem(
        extraction_id=ext_pl.id,
        item_index=1,
        sku="SKU-001",
        description_vi="Bàn ghế gỗ",
        hs_code="9403.60.90",
        quantity=100,
        uom="Bộ"
    ))

    # Document 3: Bill of Lading with container info and transport clause
    doc_bl = Document(
        shipment_id=shipment.id,
        document_type="BILL_OF_LADING",
        original_filename="surrender NBCTPPHCM261724.pdf",
        storage_path="uploads/mock_bl.pdf",
        mime_type="application/pdf",
        sha256_hash="hash3",
        file_size_bytes=1000
    )
    test_db.add(doc_bl)
    test_db.flush()

    ext_bl = DocumentExtraction(
        document_id=doc_bl.id,
        model_name="gemini-2.5-flash",
        status="SUCCESS",
        raw_response_json="{}",
        extracted_header_json=json.dumps({
            "document_number": "NBCTPPHCM261724",
            "vessel_voyage": "WAN HAI 272 / 012N",
            "container_numbers": ["TXGU7251747"],
            "seal_numbers": ["EMCQPS9244"],
            "total_packages": "222 CARTONS",
            "total_gross_weight_kg": 7515.1
        })
    )
    test_db.add(ext_bl)
    test_db.flush()

    # Even if B/L had a line item with transport summary text:
    test_db.add(ExtractedLineItem(
        extraction_id=ext_bl.id,
        item_index=1,
        sku=None,
        description_vi="DETAILS AS PER BILL OF LADING",
        quantity=222,
        uom="CARTONS"
    ))
    test_db.commit()

    # Run reconciliation
    res = reconciliation_engine.reconcile_shipment(test_db, shipment.id)

    # Must have only 1 reconciled SKU (SKU-001), ignoring the transport clause
    assert res["total_skus"] == 1
    assert res["sku_matrix"][0]["sku"] == "SKU-001"
    assert res["sku_matrix"][0]["is_matched"] is True

    # No false positive SKU errors from B/L transport clause
    db_discrepancies = test_db.query(Discrepancy).filter_by(shipment_id=shipment.id).all()
    sku_errors = [d for d in db_discrepancies if d.rule_code in ("VAL-QTY-001", "VAL-HS-001", "VAL-HS-002")]
    assert len(sku_errors) == 0
    assert len(res["sku_matrix"][0]["discrepancies"]) == 0


def test_consolidated_shipment_header_service(test_db):
    """Kiểm tra tổng hợp thông tin chung & vận chuyển toàn bộ hồ sơ kèm provenance."""
    from app.api.v1.shipments import get_consolidated_header

    # Dùng lại shipment từ test trước nếu có hoặc tạo mới
    shipment = Shipment(
        shipment_code="SHP-TEST-HEADER",
        customs_declaration_no="107894526460",
        status="VALIDATED"
    )
    test_db.add(shipment)
    test_db.commit()

    res = get_consolidated_header(shipment.id, test_db)
    assert res.shipment_code == "SHP-TEST-HEADER"
    assert res.customs_declaration_no is not None
    assert res.customs_declaration_no.value == "107894526460"

