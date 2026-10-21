import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    shipment_id: Mapped[str] = mapped_column(String(36), ForeignKey("shipments.id"), index=True)
    
    # Actions: FIELD_OVERRIDE | REVALIDATION_TRIGGERED | DISCREPANCY_RESOLVED | WMS_APPROVAL | STATUS_CHANGE
    action: Mapped[str] = mapped_column(String(64), index=True)
    target_entity: Mapped[str] = mapped_column(String(64))  # e.g. ExtractedLineItem, Discrepancy, Shipment
    target_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    
    field_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    old_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    user_id: Mapped[str] = mapped_column(String(100), default="operator")
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    shipment: Mapped["Shipment"] = relationship("Shipment", back_populates="audit_logs")
