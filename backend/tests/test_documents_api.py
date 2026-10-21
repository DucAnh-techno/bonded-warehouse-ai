"""
Phase 2 Tests: Document Upload, Parsing, and API Integration
-------------------------------------------------------------
Tests use the shared test fixtures (conftest.py):
  - client: FastAPI TestClient with overridden DB dependency
  - test_db: fresh SQLAlchemy session per test function

All file content is generated in-memory (no real files on disk required).
No Gemini/AI calls are made.
"""
from __future__ import annotations

import hashlib
import io
import json
import uuid
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers — generate minimal valid in-memory files
# ---------------------------------------------------------------------------

def _make_pdf_bytes() -> bytes:
    """Create a minimal valid single-page PDF using PyMuPDF."""
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text(
        (72, 72),
        "PACKING LIST\nSố PL: PL-2026-001\nSKU: 00123456\nSố lượng: 100 PCS",
        fontsize=12,
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _make_xlsx_bytes() -> bytes:
    """Create a minimal valid XLSX with string cells that have leading zeros."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Packing List"
    ws.append(["SKU", "Tên hàng", "Số lượng", "Đơn vị", "PO Number"])
    ws.append(["00123456", "Linh kiện điện tử", 100, "PCS", "PO-00042"])
    ws.append(["00789012", "Bo mạch chủ", 50, "PCS", "PO-00042"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _make_xls_bytes() -> bytes:
    """Create a minimal valid XLS file using xlwt (fallback: use openpyxl if xlwt absent)."""
    try:
        import xlwt
        wb = xlwt.Workbook()
        ws = wb.add_sheet("Sheet1")
        ws.write(0, 0, "SKU")
        ws.write(0, 1, "Số lượng")
        ws.write(1, 0, "00567890")
        ws.write(1, 1, 200)
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()
    except ImportError:
        # xlwt not installed — skip test via marker instead of failing
        pytest.skip("xlwt not installed, skipping XLS generation test")


def _make_shipment(client) -> str:
    """Helper: create a shipment and return its ID."""
    code = f"SHP-TEST-{uuid.uuid4().hex[:8].upper()}"
    resp = client.post(
        "/api/v1/shipments/",
        json={
            "shipment_code": code,
            "direction": "INBOUND",
            "warehouse_type": "BONDED",
        },
    )
    assert resp.status_code == 201, f"Shipment creation failed: {resp.text}"
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Tests — Upload
# ---------------------------------------------------------------------------

class TestDocumentUpload:
    def test_upload_pdf_success(self, client):
        """PDF upload should succeed, store file, compute SHA-256, detect page count."""
        shipment_id = _make_shipment(client)
        pdf_bytes = _make_pdf_bytes()
        expected_hash = hashlib.sha256(pdf_bytes).hexdigest()

        resp = client.post(
            "/api/v1/documents/upload",
            data={"shipment_id": shipment_id, "document_type": "PACKING_LIST"},
            files={"file": ("packing-list.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()

        assert data["sha256_hash"] == expected_hash
        assert data["original_filename"] == "packing-list.pdf"
        assert data["document_type"] == "PACKING_LIST"
        assert data["file_size_bytes"] == len(pdf_bytes)
        assert data["page_count"] == 1
        assert data["has_extraction"] is False
        assert "id" in data

    def test_upload_xlsx_success(self, client):
        """XLSX upload should succeed and page_count should be None."""
        shipment_id = _make_shipment(client)
        xlsx_bytes = _make_xlsx_bytes()

        resp = client.post(
            "/api/v1/documents/upload",
            data={"shipment_id": shipment_id, "document_type": "COMMERCIAL_INVOICE"},
            files={
                "file": (
                    "invoice.xlsx",
                    io.BytesIO(xlsx_bytes),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["original_filename"] == "invoice.xlsx"
        assert data["file_size_bytes"] == len(xlsx_bytes)
        # Excel files have no concept of pages; page_count should be None or absent
        assert data["page_count"] is None

    def test_upload_invalid_extension_rejected(self, client):
        """Uploading an .exe file should return 400."""
        shipment_id = _make_shipment(client)
        resp = client.post(
            "/api/v1/documents/upload",
            data={"shipment_id": shipment_id, "document_type": "OTHER"},
            files={"file": ("malware.exe", io.BytesIO(b"MZ\x90\x00"), "application/octet-stream")},
        )
        assert resp.status_code == 400
        assert "không được hỗ trợ" in resp.json()["detail"].lower()

    def test_upload_zero_byte_file_rejected(self, client):
        """Empty file should be rejected with 400."""
        shipment_id = _make_shipment(client)
        resp = client.post(
            "/api/v1/documents/upload",
            data={"shipment_id": shipment_id, "document_type": "OTHER"},
            files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")},
        )
        assert resp.status_code == 400
        assert "rỗng" in resp.json()["detail"].lower()

    def test_upload_nonexistent_shipment_returns_404(self, client):
        """Upload to a shipment that doesn't exist should return 404."""
        pdf_bytes = _make_pdf_bytes()
        resp = client.post(
            "/api/v1/documents/upload",
            data={"shipment_id": "00000000-0000-0000-0000-000000000000", "document_type": "OTHER"},
            files={"file": ("doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )
        assert resp.status_code == 404

    def test_upload_invalid_document_type_rejected(self, client):
        """Unknown document_type should return 422."""
        shipment_id = _make_shipment(client)
        pdf_bytes = _make_pdf_bytes()
        resp = client.post(
            "/api/v1/documents/upload",
            data={"shipment_id": shipment_id, "document_type": "RANDOM_GARBAGE"},
            files={"file": ("doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests — Retrieval
# ---------------------------------------------------------------------------

class TestDocumentRetrieval:
    def _upload_pdf(self, client) -> tuple[str, str]:
        """Upload a PDF and return (shipment_id, document_id)."""
        shipment_id = _make_shipment(client)
        pdf_bytes = _make_pdf_bytes()
        resp = client.post(
            "/api/v1/documents/upload",
            data={"shipment_id": shipment_id, "document_type": "PACKING_LIST"},
            files={"file": ("pl.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )
        assert resp.status_code == 201
        return shipment_id, resp.json()["id"]

    def test_get_document_by_id(self, client):
        _, doc_id = self._upload_pdf(client)
        resp = client.get(f"/api/v1/documents/{doc_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == doc_id

    def test_get_document_unknown_id_returns_404(self, client):
        resp = client.get("/api/v1/documents/nonexistent-id")
        assert resp.status_code == 404

    def test_list_shipment_documents(self, client):
        shipment_id, doc_id = self._upload_pdf(client)
        resp = client.get(f"/api/v1/documents/shipment/{shipment_id}")
        assert resp.status_code == 200
        ids = [d["id"] for d in resp.json()]
        assert doc_id in ids

    def test_override_document_type(self, client):
        _, doc_id = self._upload_pdf(client)
        resp = client.patch(
            f"/api/v1/documents/{doc_id}/type",
            json={"document_type": "CUSTOMS_DECLARATION"},
        )
        assert resp.status_code == 200
        assert resp.json()["document_type"] == "CUSTOMS_DECLARATION"

    def test_override_invalid_type_rejected(self, client):
        _, doc_id = self._upload_pdf(client)
        resp = client.patch(
            f"/api/v1/documents/{doc_id}/type",
            json={"document_type": "INVALID_TYPE"},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests — Real File Parsing (no AI)
# ---------------------------------------------------------------------------

class TestDocumentParsing:
    def test_parse_pdf_returns_blocks(self, client):
        """POST /parse on a PDF should return page blocks with bounding boxes."""
        shipment_id = _make_shipment(client)
        pdf_bytes = _make_pdf_bytes()
        upload_resp = client.post(
            "/api/v1/documents/upload",
            data={"shipment_id": shipment_id, "document_type": "PACKING_LIST"},
            files={"file": ("pl.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )
        assert upload_resp.status_code == 201
        doc_id = upload_resp.json()["id"]

        parse_resp = client.post(f"/api/v1/documents/{doc_id}/parse")
        assert parse_resp.status_code == 200
        content = parse_resp.json()

        assert content["format"] == "pdf"
        parsed = content["parsed_content"]
        assert parsed["page_count"] == 1
        assert len(parsed["pages"]) == 1

        page = parsed["pages"][0]
        assert page["page_number"] == 1
        assert "blocks" in page
        # At least some text blocks should be present
        text_blocks = [b for b in page["blocks"] if b["block_type"] == "text" and b["text"]]
        assert len(text_blocks) > 0
        # Each block must have a bbox list of 4 numbers
        for block in text_blocks:
            assert len(block["bbox"]) == 4

    def test_parse_xlsx_returns_sheets(self, client):
        """POST /parse on an XLSX should return sheet data with leading zeros preserved."""
        shipment_id = _make_shipment(client)
        xlsx_bytes = _make_xlsx_bytes()
        upload_resp = client.post(
            "/api/v1/documents/upload",
            data={"shipment_id": shipment_id, "document_type": "PACKING_LIST"},
            files={
                "file": (
                    "pl.xlsx",
                    io.BytesIO(xlsx_bytes),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
        assert upload_resp.status_code == 201
        doc_id = upload_resp.json()["id"]

        parse_resp = client.post(f"/api/v1/documents/{doc_id}/parse")
        assert parse_resp.status_code == 200
        content = parse_resp.json()

        assert content["format"] == "xlsx"
        parsed = content["parsed_content"]
        assert "sheet_names" in parsed
        assert "Packing List" in parsed["sheet_names"]

        sheet = parsed["sheets"]["Packing List"]
        assert sheet["row_count"] >= 2
        # Verify leading zeros are preserved in SKU column
        data_rows = sheet["rows"][1:]  # skip header
        sku_values = [row[0] for row in data_rows if row]
        assert "00123456" in sku_values, f"Leading zeros lost in SKU: {sku_values}"
        assert "00789012" in sku_values

    def test_get_parsed_content_before_parse_returns_404(self, client):
        """GET /parsed before calling /parse should return 404."""
        shipment_id = _make_shipment(client)
        pdf_bytes = _make_pdf_bytes()
        upload_resp = client.post(
            "/api/v1/documents/upload",
            data={"shipment_id": shipment_id, "document_type": "PACKING_LIST"},
            files={"file": ("pl.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )
        doc_id = upload_resp.json()["id"]
        resp = client.get(f"/api/v1/documents/{doc_id}/parsed")
        assert resp.status_code == 404

    def test_get_parsed_content_after_parse(self, client):
        """GET /parsed after /parse should return the stored content."""
        shipment_id = _make_shipment(client)
        pdf_bytes = _make_pdf_bytes()
        upload_resp = client.post(
            "/api/v1/documents/upload",
            data={"shipment_id": shipment_id, "document_type": "PACKING_LIST"},
            files={"file": ("pl.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        )
        doc_id = upload_resp.json()["id"]
        client.post(f"/api/v1/documents/{doc_id}/parse")

        resp = client.get(f"/api/v1/documents/{doc_id}/parsed")
        assert resp.status_code == 200
        assert resp.json()["format"] == "pdf"


class TestSafetyAndEdgeCases:
    def test_corrupted_pdf_rejected_and_not_stored(self, client):
        shipment_id = _make_shipment(client)
        resp = client.post(
            "/api/v1/documents/upload",
            data={"shipment_id": shipment_id, "document_type": "OTHER"},
            files={"file": ("broken.pdf", io.BytesIO(b"not really a pdf"), "application/pdf")},
        )
        assert resp.status_code == 400
        assert client.get(f"/api/v1/documents/shipment/{shipment_id}").json() == []

    def test_corrupted_xlsx_rejected(self, client):
        shipment_id = _make_shipment(client)
        resp = client.post(
            "/api/v1/documents/upload",
            data={"shipment_id": shipment_id, "document_type": "OTHER"},
            files={"file": ("broken.xlsx", io.BytesIO(b"PK garbage"), "application/octet-stream")},
        )
        assert resp.status_code == 400

    def test_path_traversal_filename_is_sanitized(self, client):
        shipment_id = _make_shipment(client)
        resp = client.post(
            "/api/v1/documents/upload",
            data={"shipment_id": shipment_id, "document_type": "OTHER"},
            files={"file": ("..\\..\\evil.pdf", io.BytesIO(_make_pdf_bytes()), "application/pdf")},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert ".." not in data["original_filename"]
        assert "evil.pdf" in data["original_filename"]
        from app.core.config import settings
        from app.services import storage_service
        assert storage_service.get_absolute_path(data["storage_path"]).resolve().is_relative_to(settings.UPLOAD_DIR.resolve())

    def test_original_bytes_preserved_on_download(self, client):
        shipment_id = _make_shipment(client)
        pdf_bytes = _make_pdf_bytes()
        doc_id = client.post(
            "/api/v1/documents/upload",
            data={"shipment_id": shipment_id, "document_type": "OTHER"},
            files={"file": ("a.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        ).json()["id"]
        dl = client.get(f"/api/v1/documents/{doc_id}/download")
        assert dl.status_code == 200
        assert dl.content == pdf_bytes
        pv = client.get(f"/api/v1/documents/{doc_id}/preview")
        assert pv.status_code == 200
        assert pv.headers["content-disposition"].startswith("inline")
        assert pv.content == pdf_bytes

    def test_xls_upload_and_parse_preserves_text_cells(self, client):
        xlwt = pytest.importorskip("xlwt")
        wb = xlwt.Workbook()
        ws = wb.add_sheet("S1")
        ws.write(0, 0, "SKU")
        ws.write(1, 0, "00567890")  # text cell -> must keep leading zeros
        buf = io.BytesIO()
        wb.save(buf)
        shipment_id = _make_shipment(client)
        doc_id = client.post(
            "/api/v1/documents/upload",
            data={"shipment_id": shipment_id, "document_type": "PACKING_LIST"},
            files={"file": ("a.xls", io.BytesIO(buf.getvalue()), "application/vnd.ms-excel")},
        ).json()["id"]
        parsed = client.post(f"/api/v1/documents/{doc_id}/parse").json()
        assert parsed["format"] == "xls"
        assert parsed["parsed_content"]["sheets"]["S1"]["rows"][1][0] == "00567890"


class TestProvenanceVersionAudit:
    def test_pdf_blocks_have_source_ref(self, client):
        shipment_id = _make_shipment(client)
        doc_id = client.post(
            "/api/v1/documents/upload",
            data={"shipment_id": shipment_id, "document_type": "OTHER"},
            files={"file": ("a.pdf", io.BytesIO(_make_pdf_bytes()), "application/pdf")},
        ).json()["id"]
        pages = client.post(f"/api/v1/documents/{doc_id}/parse").json()["parsed_content"]["pages"]
        for b in pages[0]["blocks"]:
            assert b["source_ref"].startswith("p1-b")

    def test_xlsx_sheet_declares_start_cell(self, client):
        shipment_id = _make_shipment(client)
        doc_id = client.post(
            "/api/v1/documents/upload",
            data={"shipment_id": shipment_id, "document_type": "OTHER"},
            files={"file": ("a.xlsx", io.BytesIO(_make_xlsx_bytes()), "application/octet-stream")},
        ).json()["id"]
        sheet = client.post(f"/api/v1/documents/{doc_id}/parse").json()["parsed_content"]["sheets"]["Packing List"]
        assert sheet["start_cell"] == "A1"
        assert sheet["rows"][0][0] == "SKU"

    def test_reupload_increments_version_without_overwrite(self, client):
        shipment_id = _make_shipment(client)
        ids = []
        for _ in range(2):
            r = client.post(
                "/api/v1/documents/upload",
                data={"shipment_id": shipment_id, "document_type": "OTHER"},
                files={"file": ("same.pdf", io.BytesIO(_make_pdf_bytes()), "application/pdf")},
            ).json()
            ids.append(r)
        assert [r["version"] for r in ids] == [1, 2]
        assert ids[0]["storage_path"] != ids[1]["storage_path"]

    def test_type_override_writes_audit_log(self, client, test_db):
        from app.models.audit import AuditLog
        shipment_id = _make_shipment(client)
        doc_id = client.post(
            "/api/v1/documents/upload",
            data={"shipment_id": shipment_id, "document_type": "OTHER"},
            files={"file": ("a.pdf", io.BytesIO(_make_pdf_bytes()), "application/pdf")},
        ).json()["id"]
        r = client.patch(
            f"/api/v1/documents/{doc_id}/type",
            json={"document_type": "PACKING_LIST", "changed_by": "tester", "reason": "đúng là PL"},
        )
        assert r.status_code == 200
        log = test_db.query(AuditLog).filter(AuditLog.target_id == doc_id).one()
        assert (log.field_name, log.old_value, log.new_value, log.user_id) == (
            "document_type", "OTHER", "PACKING_LIST", "tester")

    def test_page_image_render(self, client):
        shipment_id = _make_shipment(client)
        doc_id = client.post(
            "/api/v1/documents/upload",
            data={"shipment_id": shipment_id, "document_type": "OTHER"},
            files={"file": ("a.pdf", io.BytesIO(_make_pdf_bytes()), "application/pdf")},
        ).json()["id"]
        ok = client.get(f"/api/v1/documents/{doc_id}/pages/1/image")
        assert ok.status_code == 200 and ok.content[:4] == b"\x89PNG"
        assert client.get(f"/api/v1/documents/{doc_id}/pages/9/image").status_code == 404


REAL_DIR = Path(__file__).resolve().parents[2] / "project-reference"


class TestRealSampleFiles:
    """Uses the real files shipped in project-reference/ (skipped if absent)."""

    def _upload_and_parse(self, client, path: Path, mime: str):
        shipment_id = _make_shipment(client)
        data = path.read_bytes()
        up = client.post(
            "/api/v1/documents/upload",
            data={"shipment_id": shipment_id, "document_type": "OTHER"},
            files={"file": (path.name, io.BytesIO(data), mime)},
        )
        assert up.status_code == 201, up.text
        assert up.json()["sha256_hash"] == hashlib.sha256(data).hexdigest()
        parsed = client.post(f"/api/v1/documents/{up.json()['id']}/parse")
        assert parsed.status_code == 200, parsed.text
        return parsed.json()["parsed_content"]

    def test_real_xls(self, client):
        files = list((REAL_DIR / "wms-template").glob("*.xls"))
        if not files:
            pytest.skip("no real .xls sample")
        content = self._upload_and_parse(client, files[0], "application/vnd.ms-excel")
        assert content["format"] == "xls" and content["sheet_names"]

    def test_real_pdf(self, client):
        files = list((REAL_DIR / "warehouse-procedures").glob("*.pdf"))
        if not files:
            pytest.skip("no real .pdf sample")
        content = self._upload_and_parse(client, files[0], "application/pdf")
        assert content["format"] == "pdf" and content["page_count"] >= 1
