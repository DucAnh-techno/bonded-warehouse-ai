import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, DateTime, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Document(Base):
    """Document metadata. Original file is stored immutably on disk.
    The actual file content is not stored in the DB, only its path and checksum.
    """

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    shipment_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("shipments.id"), nullable=True, index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # file_size_bytes is the canonical column name throughout API/schema
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    document_type: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="CUSTOMS_DECLARATION | COMMERCIAL_INVOICE | PACKING_LIST | BILL_OF_LADING | PURCHASE_ORDER | CERT_OF_ORIGIN | OTHER",
    )
    # Parsed content from real file extraction (PDF blocks or Excel sheets) — no AI values
    parsed_content_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Version of this file within its shipment (same original filename uploaded again => +1).
    # Earlier versions are never overwritten or deleted.
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    extraction: Mapped[Optional["DocumentExtraction"]] = relationship(
        "DocumentExtraction", back_populates="document", uselist=False, cascade="all, delete-orphan"
    )
    shipment: Mapped[Optional["Shipment"]] = relationship("Shipment", back_populates="documents")
