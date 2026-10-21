from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict


class DocumentBase(BaseModel):
    document_type: str
    original_filename: str


class DocumentCreate(DocumentBase):
    shipment_id: str
    storage_path: str
    mime_type: str
    file_size_bytes: int
    sha256_hash: str
    page_count: Optional[int] = None


class DocumentResponse(DocumentBase):
    id: str
    shipment_id: str
    storage_path: str
    mime_type: str
    file_size_bytes: int
    sha256_hash: str
    page_count: Optional[int] = None
    uploaded_at: datetime
    version: int = 1
    has_extraction: bool = False
    has_parsed_content: bool = False

    model_config = ConfigDict(from_attributes=True)


class ParsedExtractionResponse(BaseModel):
    """Response from POST /documents/{id}/parse — real file content parsing, no AI."""
    document_id: str
    original_filename: str
    format: str  # "pdf" | "xlsx" | "xls"
    parsed_content: Dict[str, Any]

    model_config = ConfigDict(from_attributes=True)
