import uuid
from datetime import datetime, timezone, date
from typing import List, Optional
from sqlalchemy import String, DateTime, Date, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Shipment(Base):
    __tablename__ = "shipments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    shipment_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    customs_declaration_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    declaration_type: Mapped[Optional[str]] = mapped_column(String(16), default="C11")  # C11 | C21
    warehouse_type: Mapped[str] = mapped_column(String(32), default="BONDED")  # BONDED (Kho ngoại quan)
    bonded_warehouse_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default="Kho Ngoại Quan Đình Vũ - Hải Phòng")
    partner_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Doanh nghiệp đối tác / Consignee
    direction: Mapped[str] = mapped_column(String(16), default="INBOUND")  # INBOUND | OUTBOUND
    inbound_source: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # DOMESTIC (Nhập nội địa) | FOREIGN (Nhập nước ngoài)
    
    # Lifecycle: DRAFT -> EXTRACTING -> RECONCILING -> DISCREPANT -> VALIDATED -> APPROVED -> TRANSMITTED
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", index=True)
    approval_status: Mapped[str] = mapped_column(String(32), default="PENDING")  # PENDING | APPROVED | REJECTED
    approved_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    entry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    documents: Mapped[List["Document"]] = relationship("Document", back_populates="shipment", cascade="all, delete-orphan")
    discrepancies: Mapped[List["Discrepancy"]] = relationship("Discrepancy", back_populates="shipment", cascade="all, delete-orphan")
    audit_logs: Mapped[List["AuditLog"]] = relationship("AuditLog", back_populates="shipment", cascade="all, delete-orphan")
    wms_transmissions: Mapped[List["WMSTransmission"]] = relationship("WMSTransmission", back_populates="shipment", cascade="all, delete-orphan")
