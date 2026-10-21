"""
Tests for Phase 3: Gemini Document Extraction, Schema Validation, HITL Item Editing, and Error Handling.
---------------------------------------------------------------------------------------------------------
- Validates model response against typed schemas (GeminiDocumentExtractionResult).
- Missing fields must be null, never invented.
- Multi-PO -> SKU linkage.
- Granular separation of extraction per document.
- HITL editing on line items with AuditLog and dynamic revalidation trigger.
- Error handling: raises clear errors, never silently substitutes fake extraction.
- End-to-end extraction with a newly created document.
"""
import io
import json
import uuid
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.models.shipment import Shipment
from app.models.document import Document
from app.models.extraction import DocumentExtraction, ExtractedLineItem
from app.models.audit import AuditLog
from app.schemas.extraction import GeminiDocumentExtractionResult, GeminiLineItemExtraction


def _make_pdf_bytes() -> bytes:
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 72), "COMMERCIAL INVOICE\nINV-2026-001\nUSD 5000", fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _create_test_shipment(test_db):
    shipment = Shipment(
        shipment_code=f"SHP-EXTRACT-{uuid.uuid4().hex[:6].upper()}",
        direction="INBOUND",
        warehouse_type="BONDED"
    )
    test_db.add(shipment)
    test_db.commit()
    test_db.refresh(shipment)
    return shipment


def test_gemini_schema_validation_preserves_nulls():
    """Verify that schema validation preserves nulls and does not invent missing fields."""
    payload = {
        "document_type_detected": "COMMERCIAL_INVOICE",
        "document_number": "INV-2026-999",
        "issue_date": "2026-03-15",
        "shipper_exporter": "Global Logistics Co.",
        # Missing fields should default to None/null
        "consignee_importer": None,
        "warehouse_name": None,
        "vessel_voyage": None,
        "container_numbers": [],
        "seal_numbers": [],
        "total_gross_weight_kg": None,
        "total_net_weight_kg": None,
        "total_invoice_value": 4500.0,
        "currency": "USD",
        "incoterms": "CIF",
        "items": [
            {
                "item_index": 1,
                "sku": "SKU-AUTO-01",
                "part_number": None,
                "description_vi": "Cụm vi xử lý công nghiệp",
                "hs_code": "8471.49.10",
                "quantity": 100.0,
                "uom": "PCS",
                "unit_price": 45.0,
                "total_amount": 4500.0,
                "currency": "USD",
                "gross_weight_kg": None,
                "net_weight_kg": None,
                "po_reference": "PO-2026-008",
                "page_number": 1,
                "raw_line_text": "Item 1: SKU-AUTO-01 Processor Qty 100 @ 45 USD PO-2026-008"
            }
        ]
    }

    result = GeminiDocumentExtractionResult.model_validate(payload)
    assert result.document_number == "INV-2026-999"
    assert result.consignee_importer is None
    assert result.total_gross_weight_kg is None
    assert len(result.items) == 1
    assert result.items[0].po_reference == "PO-2026-008"
    assert result.items[0].gross_weight_kg is None
    assert result.items[0].raw_line_text is not None


def test_extract_endpoint_refuses_fake_data_when_api_fails(client, test_db):
    """When the Gemini API fails, it must raise a descriptive error and NEVER return fake data."""
    shipment = _create_test_shipment(test_db)
    
    # Upload a document
    doc_resp = client.post(
        "/api/v1/documents/upload",
        data={"shipment_id": shipment.id, "document_type": "COMMERCIAL_INVOICE"},
        files={"file": ("invoice_test.pdf", io.BytesIO(_make_pdf_bytes()), "application/pdf")}
    )
    assert doc_resp.status_code == 201
    doc_id = doc_resp.json()["id"]

    # Mock GeminiExtractorService to simulate API failure
    with patch("app.services.gemini_extractor.extract_document", side_effect=RuntimeError("Google Gemini API quota exceeded or connection refused")):
        resp = client.post(f"/api/v1/extractions/extract/{doc_id}")
        assert resp.status_code == 500
        error_detail = resp.json()["detail"]
        assert "Gemini" in error_detail
        assert "thử lại" in error_detail

    # Verify no fake extraction record was silently stored
    get_resp = client.get(f"/api/v1/extractions/document/{doc_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "FAILED"
    assert get_resp.json()["line_items"] == []


def test_successful_extraction_with_new_unseen_document(client, test_db):
    """Simulate successful Gemini extraction on a new document with multi-PO and SKU structure."""
    shipment = _create_test_shipment(test_db)
    
    doc_resp = client.post(
        "/api/v1/documents/upload",
        data={"shipment_id": shipment.id, "document_type": "PACKING_LIST"},
        files={"file": ("new_shipment_pl.pdf", io.BytesIO(_make_pdf_bytes()), "application/pdf")}
    )
    assert doc_resp.status_code == 201
    doc_id = doc_resp.json()["id"]

    # Mock realistic Gemini extraction result
    mock_extraction = GeminiDocumentExtractionResult(
        document_type_detected="PACKING_LIST",
        document_number="PL-VN-2026-888",
        issue_date="2026-04-01",
        shipper_exporter="Shenzhen Tech Export Ltd",
        consignee_importer="Hai Phong Logistics Warehouse JSC",
        warehouse_name="Kho Ngoại Quan Đình Vũ",
        container_numbers=["TGHU9988776"],
        seal_numbers=["SEAL-00123"],
        total_gross_weight_kg=1250.0,
        total_net_weight_kg=1100.0,
        total_packages=50,
        items=[
            GeminiLineItemExtraction(
                item_index=1,
                sku="SKU-CHIP-A",
                part_number="PN-991",
                description_vi="Bo mạch điều khiển trung tâm",
                hs_code="8542.31.00",
                quantity=500.0,
                uom="PCS",
                unit_price=12.5,
                total_amount=6250.0,
                gross_weight_kg=600.0,
                net_weight_kg=550.0,
                po_reference="PO-ALPHA-01",
                page_number=1,
                raw_line_text="1 | SKU-CHIP-A | Bo mach dieu khien | 500 PCS | 12.5 USD | PO-ALPHA-01"
            ),
            GeminiLineItemExtraction(
                item_index=2,
                sku="SKU-CHIP-B",
                part_number=None,
                description_vi="Cảm biến quang học chính xác cao",
                hs_code=None,  # Missing field is None
                quantity=300.0,
                uom="PCS",
                unit_price=20.0,
                total_amount=6000.0,
                gross_weight_kg=650.0,
                net_weight_kg=550.0,
                po_reference="PO-BETA-02",  # Different PO under the same shipment
                page_number=1,
                raw_line_text="2 | SKU-CHIP-B | Cam bien quang hoc | 300 PCS | 20.0 USD | PO-BETA-02"
            )
        ]
    )

    with patch("app.services.gemini_extractor.extract_document", new_callable=AsyncMock) as mock_extract:
        mock_extract.return_value = (mock_extraction, {"prompt_tokens": 1250, "candidate_tokens": 420})
        
        resp = client.post(f"/api/v1/extractions/extract/{doc_id}")
        assert resp.status_code == 200
        data = resp.json()

        assert data["document_id"] == doc_id
        assert data["status"] == "SUCCESS"
        assert data["prompt_tokens"] == 1250
        assert data["candidate_tokens"] == 420
        assert len(data["line_items"]) == 2

        item1 = data["line_items"][0]
        assert item1["sku"] == "SKU-CHIP-A"
        assert item1["po_reference"] == "PO-ALPHA-01"
        assert item1["quantity"] == 500.0

        item2 = data["line_items"][1]
        assert item2["sku"] == "SKU-CHIP-B"
        assert item2["po_reference"] == "PO-BETA-02"
        assert item2["hs_code"] is None  # Preserved as null


def test_hitl_field_editing_with_audit_trail_and_revalidation(client, test_db):
    """Test manual editing of extracted SKU line items with AuditLog tracking."""
    shipment = _create_test_shipment(test_db)
    
    # Setup document and extraction record
    doc = Document(
        shipment_id=shipment.id,
        document_type="COMMERCIAL_INVOICE",
        original_filename="inv.pdf",
        storage_path="storage/uploads/inv.pdf",
        mime_type="application/pdf",
        sha256_hash="dummyhash",
        file_size_bytes=1000
    )
    test_db.add(doc)
    test_db.commit()

    extraction = DocumentExtraction(
        document_id=doc.id,
        status="SUCCESS",
        model_name="gemini-2.5-flash",
        raw_response_json="{}"
    )
    test_db.add(extraction)
    test_db.commit()

    line_item = ExtractedLineItem(
        extraction_id=extraction.id,
        item_index=1,
        sku="SKU-OCR-TYPO",
        description_vi="Màn hình tinh thể lỏng",
        quantity=95.0,
        unit_price=100.0,
        total_amount=9500.0,
        hs_code="8528.52.00"
    )
    test_db.add(line_item)
    test_db.commit()
    test_db.refresh(line_item)

    # Operator performs correction: corrects quantity from 95.0 to 100.0 and SKU code
    patch_payload = {
        "sku": "SKU-CORRECT-100",
        "quantity": 100.0,
        "total_amount": 10000.0,
        "reason": "Sửa lỗi OCR từ tệp hóa đơn gốc trang 1"
    }

    resp = client.patch(
        f"/api/v1/extractions/items/{line_item.id}?user_id=customs_officer_nam",
        json=patch_payload
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["sku"] == "SKU-CORRECT-100"
    assert updated["quantity"] == 100.0

    # Verify AuditLog entries were created
    audit_logs = test_db.query(AuditLog).filter(
        AuditLog.shipment_id == shipment.id,
        AuditLog.target_id == line_item.id
    ).all()
    
    assert len(audit_logs) >= 2  # SKU, quantity, and total_amount
    sku_audit = next((a for a in audit_logs if a.field_name == "sku"), None)
    assert sku_audit is not None
    assert sku_audit.old_value == "SKU-OCR-TYPO"
    assert sku_audit.new_value == "SKU-CORRECT-100"
    assert sku_audit.user_id == "customs_officer_nam"
    assert "Sửa lỗi OCR" in sku_audit.reason


def test_batch_reconcile_shipment_endpoint_single_prompt(client, test_db):
    """Verify single-prompt batch extraction and reconciliation of all shipment documents."""
    from app.schemas.extraction import BatchShipmentReconciliationResult, PerDocumentExtraction, ReconciledDiscrepancy

    shipment = _create_test_shipment(test_db)

    # Add 2 documents
    file_bytes = _make_pdf_bytes()
    resp1 = client.post(
        "/api/v1/documents/upload",
        data={"shipment_id": shipment.id, "document_type": "COMMERCIAL_INVOICE"},
        files={"file": ("invoice_batch.pdf", io.BytesIO(file_bytes), "application/pdf")},
    )
    assert resp1.status_code == 201
    doc1_id = resp1.json()["id"]

    resp2 = client.post(
        "/api/v1/documents/upload",
        data={"shipment_id": shipment.id, "document_type": "PACKING_LIST"},
        files={"file": ("packing_batch.pdf", io.BytesIO(file_bytes), "application/pdf")},
    )
    assert resp2.status_code == 201
    doc2_id = resp2.json()["id"]

    mock_batch_result = BatchShipmentReconciliationResult(
        shipment_code=shipment.shipment_code,
        customs_declaration_no="105928374610",
        overall_validity="VALID",
        validity_reason="Toàn bộ số lượng và đơn giá giữa Invoice và Packing List hoàn toàn khớp.",
        discrepancies=[],
        documents=[
            PerDocumentExtraction(
                document_id=doc1_id,
                document_type_detected="COMMERCIAL_INVOICE",
                document_number="INV-BATCH-001",
                total_invoice_value=5000.0,
                currency="USD",
                items=[
                    GeminiLineItemExtraction(
                        item_index=1,
                        sku="SKU-BATCH-A",
                        description_vi="Màn hình Dell UltraSharp",
                        quantity=50.0,
                        uom="SET",
                        unit_price=100.0,
                        total_amount=5000.0
                    )
                ]
            ),
            PerDocumentExtraction(
                document_id=doc2_id,
                document_type_detected="PACKING_LIST",
                document_number="PL-BATCH-001",
                total_packages=50,
                items=[
                    GeminiLineItemExtraction(
                        item_index=1,
                        sku="SKU-BATCH-A",
                        description_vi="Màn hình Dell UltraSharp",
                        quantity=50.0,
                        uom="SET"
                    )
                ]
            )
        ]
    )

    with patch(
        "app.api.v1.extractions.gemini_extractor.batch_extract_and_reconcile_shipment",
        new=AsyncMock(return_value=(mock_batch_result, {"prompt_tokens": 1500, "candidate_tokens": 600}))
    ):
        batch_resp = client.post(f"/api/v1/extractions/shipment/{shipment.id}/batch-reconcile")
        assert batch_resp.status_code == 200
        data = batch_resp.json()
        assert data["overall_validity"] == "INVALID"  # Mock AI verdict cannot waive the missing lease.
        assert data["customs_declaration_no"] == "105928374610"
        assert len(data["documents"]) == 2

    # Verify database extractions were saved for each document
    ext1 = test_db.query(DocumentExtraction).filter(DocumentExtraction.document_id == doc1_id).first()
    assert ext1 is not None
    assert len(ext1.line_items) == 1
    assert ext1.line_items[0].sku == "SKU-BATCH-A"

    ext2 = test_db.query(DocumentExtraction).filter(DocumentExtraction.document_id == doc2_id).first()
    assert ext2 is not None
    assert len(ext2.line_items) == 1


def test_delete_shipment_removes_physical_files_and_db(client, test_db):
    """Verify DELETE /shipments/{id} removes database rows and cleans physical files from disk."""
    from app.services import storage_service

    shipment = _create_test_shipment(test_db)
    file_bytes = _make_pdf_bytes()
    resp = client.post(
        "/api/v1/documents/upload",
        data={"shipment_id": shipment.id, "document_type": "CERT_OF_ORIGIN"},
        files={"file": ("co_test_delete.pdf", io.BytesIO(file_bytes), "application/pdf")},
    )
    assert resp.status_code == 201
    doc_path = resp.json()["storage_path"]
    abs_file = storage_service.get_absolute_path(doc_path)
    assert abs_file.exists()

    # Delete shipment
    del_resp = client.delete(f"/api/v1/shipments/{shipment.id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True

    # Verify physical file was deleted
    assert not abs_file.exists()

    # Verify shipment is gone from DB
    assert test_db.query(Shipment).filter(Shipment.id == shipment.id).first() is None

