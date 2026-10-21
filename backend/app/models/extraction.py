import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, DateTime, ForeignKey, Integer, Float, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class DocumentExtraction(Base):
    __tablename__ = "document_extractions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), unique=True, index=True)
    
    # Status: PENDING | SUCCESS | FAILED
    status: Mapped[str] = mapped_column(String(32), default="PENDING")
    model_name: Mapped[str] = mapped_column(String(64))  # e.g. gemini-2.5-flash
    raw_response_json: Mapped[str] = mapped_column(Text)  # Exact structured response from Gemini
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Extracted Header Entities (stored as normalized JSON for quick query)
    extracted_header_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    extracted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    version: Mapped[int] = mapped_column(Integer, default=1)
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    candidate_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="extraction")
    line_items: Mapped[List["ExtractedLineItem"]] = relationship("ExtractedLineItem", back_populates="extraction", cascade="all, delete-orphan")


class ExtractedLineItem(Base):
    __tablename__ = "extracted_line_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    extraction_id: Mapped[str] = mapped_column(String(36), ForeignKey("document_extractions.id"), index=True)
    
    item_index: Mapped[int] = mapped_column(Integer, default=1)
    sku: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    part_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description_vi: Mapped[str] = mapped_column(String(500))  # Tên hàng bằng tiếng Việt / tiếng Anh
    hs_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)  # Mã HS 8 số
    
    quantity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    uom: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # Đơn vị tính: PCS, KG, BOX...
    unit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    
    gross_weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    net_weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    po_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)  # Số PO đối ứng
    page_number: Mapped[Optional[int]] = mapped_column(Integer, default=1)
    raw_line_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Nguyên văn dòng trích xuất
    bounding_box_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Coordinates if available

    extraction: Mapped["DocumentExtraction"] = relationship("DocumentExtraction", back_populates="line_items")
