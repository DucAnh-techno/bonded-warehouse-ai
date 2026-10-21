import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class Discrepancy(Base):
    __tablename__ = "discrepancies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    shipment_id: Mapped[str] = mapped_column(String(36), ForeignKey("shipments.id"), index=True)
    
    # Rule identification
    rule_code: Mapped[str] = mapped_column(String(32), index=True)  # e.g. VAL-QTY-001, VAL-HS-001
    severity: Mapped[str] = mapped_column(String(16))  # ERROR (blocking WMS) | WARNING (advisory)
    field_name: Mapped[str] = mapped_column(String(100))
    description_vi: Mapped[str] = mapped_column(Text)
    
    # Conflict classification: MISSING | CONFLICT | NOT_APPLICABLE | NOT_VERIFIED
    category: Mapped[Optional[str]] = mapped_column(String(32), default="CONFLICT", nullable=True)

    # Conflict comparison (Side-by-Side)
    source_doc_a_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    source_doc_a_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    value_a: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    source_doc_b_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    source_doc_b_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    value_b: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Resolution (NEVER automatic - strictly Human-In-The-Loop)
    # Status: OPEN | OVERRIDDEN | ACCEPTED | REJECTED
    status: Mapped[str] = mapped_column(String(32), default="OPEN", index=True)
    resolution_action: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    resolution_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    shipment: Mapped["Shipment"] = relationship("Shipment", back_populates="discrepancies")


class ValidationRuleSetting(Base):
    __tablename__ = "validation_rule_settings"

    rule_code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name_vi: Mapped[str] = mapped_column(String(255))
    description_vi: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(16), default="ERROR")  # ERROR | WARNING | INFO
    enabled: Mapped[bool] = mapped_column(default=True)
    tolerance: Mapped[Optional[float]] = mapped_column(nullable=True)
    category: Mapped[str] = mapped_column(String(32), default="CONFLICT")  # MISSING | CONFLICT | NOT_APPLICABLE | NOT_VERIFIED
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)



class WMSTransmission(Base):
    __tablename__ = "wms_transmissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    shipment_id: Mapped[str] = mapped_column(String(36), ForeignKey("shipments.id"), index=True)
    
    # Gatekeeper status: BLOCKED | READY | TRANSMITTED | FAILED
    status: Mapped[str] = mapped_column(String(32), default="BLOCKED", index=True)
    is_blocked: Mapped[bool] = mapped_column(default=True)
    blocking_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    approved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Standardized inbound WMS JSON
    wms_endpoint: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    wms_response_code: Mapped[Optional[int]] = mapped_column(nullable=True)
    wms_response_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    transmitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    shipment: Mapped["Shipment"] = relationship("Shipment", back_populates="wms_transmissions")
