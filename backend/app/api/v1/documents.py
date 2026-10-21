"""
Documents API — Phase 2
-----------------------
POST /documents/upload     — Upload & store immutable document file
GET  /documents/{id}       — Get document metadata by ID
GET  /documents/shipment/{id} — List all documents for a shipment
GET  /documents/{id}/download — Download original file
PATCH /documents/{id}/type — Override document category (user override)
POST /documents/{id}/parse — Trigger real file parsing (PDF/Excel)
GET  /documents/{id}/parsed — Retrieve stored parsed content
"""
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Body, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.shipment import Shipment
from app.models.document import Document
from app.schemas.document import DocumentResponse, ParsedExtractionResponse
from app.services import storage_service
from app.services.validation.documents import invalidate_approval
from app.services.document_parser.parser import document_parser

router = APIRouter(prefix="/documents", tags=["Documents"])

ALLOWED_DOCUMENT_TYPES = {
    "CUSTOMS_DECLARATION",
    "COMMERCIAL_INVOICE",
    "PACKING_LIST",
    "BILL_OF_LADING",
    "ARRIVAL_NOTICE",
    "SALE_CONTRACT",
    "PURCHASE_ORDER",
    "CERT_OF_ORIGIN",
    "WAREHOUSE_CONTRACT",
    "OTHER",
}


def _to_response(doc: Document) -> DocumentResponse:
    return DocumentResponse(
        id=doc.id,
        shipment_id=doc.shipment_id or "",
        document_type=doc.document_type or "OTHER",
        original_filename=doc.original_filename,
        storage_path=doc.storage_path,
        mime_type=doc.mime_type,
        file_size_bytes=doc.file_size_bytes,
        sha256_hash=doc.sha256_hash,
        page_count=doc.page_count,
        uploaded_at=doc.uploaded_at,
        version=doc.version or 1,
        has_extraction=doc.extraction is not None and doc.extraction.status == "SUCCESS",
        has_parsed_content=doc.parsed_content_json is not None,
    )


# ---------------------------------------------------------------------------
# POST /documents/upload
# ---------------------------------------------------------------------------
@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    shipment_id: str = Form(...),
    document_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload an immutable document file, compute SHA-256, detect page count for PDFs."""
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy lô hàng để gắn chứng từ.",
        )

    if document_type not in ALLOWED_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Loại chứng từ '{document_type}' không hợp lệ. "
                   f"Chọn một trong: {sorted(ALLOWED_DOCUMENT_TYPES)}",
        )

    from app.core.config import settings
    if settings.DEMO_ONLY:
        import hashlib
        body = await file.read(settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024 + 1)
        await file.seek(0)
        allowed_hashes = {hashlib.sha256(p.read_bytes()).hexdigest() for p in settings.DEMO_SAMPLES_DIR.glob("*") if p.is_file()}
        if hashlib.sha256(body).hexdigest() not in allowed_hashes:
            raise HTTPException(400, "Bản demo online chỉ nhận bộ chứng từ mẫu tải từ giao diện.")

    try:
        rel_path, orig_name, size_bytes, sha256_hash, page_count = (
            await storage_service.save_uploaded_file(file)
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # Determine MIME type from extension if browser didn't provide it
    detected_mime = document_parser.get_mime_type(orig_name)
    mime_type = file.content_type or detected_mime
    if mime_type == "application/octet-stream":
        mime_type = detected_mime

    previous_versions = (
        db.query(Document)
        .filter(Document.shipment_id == shipment_id, Document.original_filename == orig_name)
        .count()
    )

    doc = Document(
        shipment_id=shipment_id,
        document_type=document_type,
        original_filename=orig_name,
        storage_path=rel_path,
        mime_type=mime_type,
        file_size_bytes=size_bytes,
        sha256_hash=sha256_hash,
        page_count=page_count,
        version=previous_versions + 1,
    )
    db.add(doc)
    invalidate_approval(shipment)
    db.commit()
    db.refresh(doc)
    return _to_response(doc)


# ---------------------------------------------------------------------------
# GET /documents/{document_id}
# ---------------------------------------------------------------------------
@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy chứng từ.",
        )
    return _to_response(doc)


# ---------------------------------------------------------------------------
# GET /documents/shipment/{shipment_id}
# ---------------------------------------------------------------------------
@router.get("/shipment/{shipment_id}", response_model=List[DocumentResponse])
def get_shipment_documents(shipment_id: str, db: Session = Depends(get_db)):
    docs = db.query(Document).filter(Document.shipment_id == shipment_id).all()
    return [_to_response(d) for d in docs]


# ---------------------------------------------------------------------------
# GET /documents/{document_id}/download
# ---------------------------------------------------------------------------
@router.get("/{document_id}/download")
def download_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy chứng từ.",
        )

    abs_path = storage_service.get_absolute_path(doc.storage_path)
    if not abs_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tệp chứng từ gốc không tồn tại trên ổ đĩa.",
        )

    return FileResponse(
        path=str(abs_path),
        filename=doc.original_filename,
        media_type=doc.mime_type,
    )


# ---------------------------------------------------------------------------
# GET /documents/{document_id}/preview  — Inline display (original bytes, unmodified)
# ---------------------------------------------------------------------------
@router.get("/{document_id}/preview")
def preview_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy chứng từ.")
    abs_path = storage_service.get_absolute_path(doc.storage_path)
    if not abs_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tệp chứng từ gốc không tồn tại trên ổ đĩa.")
    return FileResponse(
        path=str(abs_path),
        filename=doc.original_filename,
        media_type=doc.mime_type,
        content_disposition_type="inline",
    )


# ---------------------------------------------------------------------------
# PATCH /documents/{document_id}/type  — User override document category
# ---------------------------------------------------------------------------
@router.patch("/{document_id}/type", response_model=DocumentResponse)
def override_document_type(
    document_id: str,
    document_type: str = Body(...),
    changed_by: str = Body("operator"),
    reason: Optional[str] = Body(None),
    db: Session = Depends(get_db),
):
    """Allow operator to correct/override the document category; recorded in AuditLog."""
    if document_type not in ALLOWED_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Loại chứng từ '{document_type}' không hợp lệ.",
        )
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy chứng từ.",
        )
    old_type = doc.document_type
    if old_type != document_type:
        invalidate_approval(doc.shipment)
        doc.document_type = document_type
        if doc.shipment_id:
            db.add(
                AuditLog(
                    shipment_id=doc.shipment_id,
                    action="FIELD_OVERRIDE",
                    target_entity="Document",
                    target_id=doc.id,
                    field_name="document_type",
                    old_value=old_type,
                    new_value=document_type,
                    user_id=changed_by,
                    reason=reason or "Người dùng đổi loại chứng từ",
                )
            )
        db.commit()
        db.refresh(doc)
    return _to_response(doc)


# ---------------------------------------------------------------------------
# GET /documents/{document_id}/pages/{page_number}/image — derived render of a PDF page
# ---------------------------------------------------------------------------
@router.get("/{document_id}/pages/{page_number}/image")
def render_pdf_page(document_id: str, page_number: int, scale: float = 1.5, db: Session = Depends(get_db)):
    """Render one PDF page to PNG (read-only; the stored original is untouched).

    Page coordinates match the bbox values returned by /parse (PDF points), so the
    UI can overlay source boxes exactly.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy chứng từ.")
    abs_path = storage_service.get_absolute_path(doc.storage_path)
    if abs_path.suffix.lower() != ".pdf" or not abs_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không có tệp PDF để hiển thị.")
    scale = max(0.5, min(scale, 3.0))
    import fitz

    try:
        with fitz.open(str(abs_path)) as pdf:
            if page_number < 1 or page_number > pdf.page_count:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Số trang không hợp lệ.")
            png = pdf[page_number - 1].get_pixmap(matrix=fitz.Matrix(scale, scale)).tobytes("png")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Không thể hiển thị trang: {exc}")
    return Response(content=png, media_type="image/png")


# ---------------------------------------------------------------------------
# POST /documents/{document_id}/parse  — Real file parsing (no AI)
# ---------------------------------------------------------------------------
@router.post("/{document_id}/parse", response_model=ParsedExtractionResponse)
def parse_document_content(document_id: str, db: Session = Depends(get_db)):
    """
    Trigger real parsing of uploaded file content using PyMuPDF (PDF) or
    openpyxl/xlrd (Excel). Stores raw parsed JSON and returns it.
    No AI/Gemini calls are made here.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy chứng từ.",
        )

    abs_path = storage_service.get_absolute_path(doc.storage_path)
    if not abs_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tệp chứng từ gốc không tồn tại trên ổ đĩa.",
        )

    suffix = abs_path.suffix.lower()
    if suffix not in (".pdf", ".xlsx", ".xls"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Chỉ hỗ trợ phân tích nội dung PDF, XLSX, XLS. "
                   f"Tệp '{doc.original_filename}' có định dạng '{suffix}' không được hỗ trợ ở bước này.",
        )

    try:
        parsed_data = document_parser.parse(abs_path)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Lỗi phân tích tệp: {exc}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi không xác định khi phân tích: {exc}",
        )

    # Persist parsed JSON to the document record
    doc.parsed_content_json = json.dumps(parsed_data, ensure_ascii=False, default=str)
    db.commit()
    db.refresh(doc)

    return ParsedExtractionResponse(
        document_id=doc.id,
        original_filename=doc.original_filename,
        format=parsed_data.get("format", suffix.lstrip(".")),
        parsed_content=parsed_data,
    )


# ---------------------------------------------------------------------------
# GET /documents/{document_id}/parsed  — Retrieve stored parsed content
# ---------------------------------------------------------------------------
@router.get("/{document_id}/parsed", response_model=ParsedExtractionResponse)
def get_parsed_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy chứng từ.",
        )
    if not doc.parsed_content_json:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chứng từ chưa được phân tích nội dung. Gọi POST /parse trước.",
        )
    parsed_data = json.loads(doc.parsed_content_json)
    return ParsedExtractionResponse(
        document_id=doc.id,
        original_filename=doc.original_filename,
        format=parsed_data.get("format", "unknown"),
        parsed_content=parsed_data,
    )
