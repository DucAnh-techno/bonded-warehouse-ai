import json
from datetime import datetime
from typing import List
from sqlalchemy.orm import Session
from app.models.shipment import Shipment
from app.models.document import Document
from app.services.validation.documents import latest_documents
from app.schemas.wms import WMSInboundReceiptPayload, WMSLineItemPayload


class WMSPayloadBuilder:
    """Builds standardized WMS Inbound/Outbound Receipt JSON payloads."""

    @staticmethod
    def build_inbound_receipt_payload(db: Session, shipment: Shipment) -> WMSInboundReceiptPayload:
        line_items: List[WMSLineItemPayload] = []
        documents = latest_documents(db.query(Document).filter(Document.shipment_id == shipment.id).all())
        
        shipper = None
        consignee = None
        carrier_vessel = None
        containers: List[str] = []
        seals: List[str] = []
        total_packages = None
        total_gross_weight = None

        for doc in documents:
            if not doc.extraction or not doc.extraction.extracted_header_json:
                continue
            try:
                hdr = json.loads(doc.extraction.extracted_header_json)
                if not shipper and (hdr.get("shipper") or hdr.get("seller_name") or hdr.get("exporter_name")):
                    shipper = hdr.get("shipper") or hdr.get("seller_name") or hdr.get("exporter_name")
                if not consignee and (hdr.get("consignee") or hdr.get("buyer_name") or hdr.get("importer_name")):
                    consignee = hdr.get("consignee") or hdr.get("buyer_name") or hdr.get("importer_name")
                if not carrier_vessel and hdr.get("vessel_voyage"):
                    carrier_vessel = hdr.get("vessel_voyage")
                if hdr.get("container_numbers"):
                    for c in hdr["container_numbers"]:
                        if c and str(c) not in containers:
                            containers.append(str(c))
                if hdr.get("seal_numbers"):
                    for s in hdr["seal_numbers"]:
                        if s and str(s) not in seals:
                            seals.append(str(s))
                if total_packages is None and hdr.get("total_packages"):
                    try:
                        raw_pkg = hdr["total_packages"]
                        if isinstance(raw_pkg, (int, float)):
                            total_packages = int(raw_pkg)
                        elif isinstance(raw_pkg, str):
                            # e.g. "222 CARTONS"
                            import re
                            m = re.search(r"\d+", raw_pkg)
                            if m:
                                total_packages = int(m.group(0))
                    except Exception:
                        pass
                if total_gross_weight is None and hdr.get("total_gross_weight_kg"):
                    try:
                        total_gross_weight = float(hdr["total_gross_weight_kg"])
                    except Exception:
                        pass
            except Exception:
                pass

        # Primary SKU lines from Customs Declaration, or fallback to Commercial Invoice
        invoice_items = [item for doc in documents if doc.document_type == "COMMERCIAL_INVOICE"
                         and doc.extraction and doc.extraction.status == "SUCCESS" for item in doc.extraction.line_items]

        counter = 1
        if invoice_items:
            for item in invoice_items:
                line_items.append(
                    WMSLineItemPayload(
                        line_number=counter,
                        sku=str(item.sku or item.part_number or f"SKU-{counter}").strip(),
                        part_number=str(item.part_number).strip() if item.part_number else None,
                        item_description=str(item.description_vi or f"Dòng hàng {counter}").strip(),
                        hs_code=str(item.hs_code).strip() if item.hs_code else None,
                        quantity=float(item.quantity) if item.quantity is not None else 0.0,
                        uom=str(item.uom or "PCS").strip().upper(),
                        po_number=str(item.po_reference).strip() if item.po_reference else None,
                        customs_declaration_no=str(shipment.customs_declaration_no or "").strip(),
                        unit_price=float(item.unit_price) if item.unit_price is not None else None,
                        currency=str(item.currency or "USD").strip().upper(),
                        net_weight_kg=float(item.net_weight_kg) if item.net_weight_kg is not None else None,
                        gross_weight_kg=float(item.gross_weight_kg) if item.gross_weight_kg is not None else None,
                    )
                )
                counter += 1

        return WMSInboundReceiptPayload(
            receipt_id=f"WMS-RCPT-{shipment.shipment_code}",
            shipment_code=shipment.shipment_code,
            customs_declaration_no=shipment.customs_declaration_no or "",
            warehouse_type=shipment.warehouse_type or "BONDED",
            receipt_date=datetime.utcnow().strftime("%Y-%m-%d"),
            shipper=shipper,
            consignee=consignee or shipment.partner_name,
            carrier_vessel=carrier_vessel,
            containers=containers,
            seals=seals,
            total_packages=total_packages,
            total_gross_weight_kg=total_gross_weight,
            total_line_items=len(line_items),
            line_items=line_items
        )


payload_builder = WMSPayloadBuilder()

