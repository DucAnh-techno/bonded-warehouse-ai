import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, DateTime, ForeignKey, Text, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class WMSReceipt(Base):
    """
    Persistent record of an inbound receipt created within the mock WMS.
    Preserves exact receipt state, headers, line items and timestamps.
    Supports idempotent processing by receipt_number and idempotency_key.
    """
    __tablename__ = "wms_receipts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    receipt_number: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    
    shipment_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("shipments.id"), nullable=True, index=True)
    shipment_code: Mapped[str] = mapped_column(String(64), index=True)
    customs_declaration_no: Mapped[str] = mapped_column(String(64), index=True)
    warehouse_type: Mapped[str] = mapped_column(String(32), default="BONDED")
    warehouse_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Status: RECEIVED | PROCESSED | CANCELLED
    status: Mapped[str] = mapped_column(String(32), default="RECEIVED", index=True)
    receipt_date: Mapped[str] = mapped_column(String(32))
    
    shipper: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    consignee: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    carrier_vessel: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    containers_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    seals_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    total_packages: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_gross_weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_net_weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_line_items: Mapped[int] = mapped_column(Integer, default=0)
    total_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(16), default="USD")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items: Mapped[List["WMSReceiptItem"]] = relationship(
        "WMSReceiptItem", 
        back_populates="receipt", 
        cascade="all, delete-orphan",
        order_by="WMSReceiptItem.line_number"
    )


class WMSReceiptItem(Base):
    """
    Individual SKU line item within a persistent WMS Inbound Receipt.
    Preserves text codes with leading zeros (SKU, HS Code).
    """
    __tablename__ = "wms_receipt_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    receipt_id: Mapped[str] = mapped_column(String(36), ForeignKey("wms_receipts.id"), index=True)
    
    line_number: Mapped[int] = mapped_column(Integer)
    sku: Mapped[str] = mapped_column(String(64), index=True)
    part_number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    item_description: Mapped[str] = mapped_column(Text)
    hs_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    quantity: Mapped[float] = mapped_column(Float)
    uom: Mapped[str] = mapped_column(String(32), default="PCS")
    unit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(16), default="USD")
    
    po_number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    customs_declaration_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    net_weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gross_weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bin_location: Mapped[Optional[str]] = mapped_column(String(64), default="RACK-A-01-01")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    receipt: Mapped["WMSReceipt"] = relationship("WMSReceipt", back_populates="items")
