"""Shared document selection for validation and export."""
from app.models.document import Document


DOMESTIC_REQUIRED_DOCUMENTS = {
    "PACKING_LIST": "Phiếu đóng gói hàng hóa (Packing List)",
    "CUSTOMS_DECLARATION": "Tờ khai hải quan",
    "COMMERCIAL_INVOICE": "Hóa đơn thương mại (Invoice)",
}

FOREIGN_REQUIRED_DOCUMENTS = {
    "BILL_OF_LADING": "Vận đơn (Bill of Lading)",
    "ARRIVAL_NOTICE": "Thông báo hàng đến (Arrival Notice)",
    "COMMERCIAL_INVOICE": "Hóa đơn thương mại (Invoice)",
    "PACKING_LIST": "Phiếu đóng gói hàng hóa (Packing List)",
    "CUSTOMS_DECLARATION": "Tờ khai hải quan",
    "WAREHOUSE_CONTRACT": "Hợp đồng thuê kho",
}

OPTIONAL_DOCUMENTS = {
    "SALE_CONTRACT": "Hợp đồng ngoại thương (Sale Contract - SC)",
    "PURCHASE_ORDER": "Đơn đặt hàng / Hợp đồng mua bán (SC / PO)",
    "CERT_OF_ORIGIN": "Giấy chứng nhận xuất xứ (C/O)",
}

# Backward compatibility alias
REQUIRED_DOCUMENTS = DOMESTIC_REQUIRED_DOCUMENTS


def get_required_documents(inbound_source: str | None) -> dict[str, str]:
    if inbound_source == "DOMESTIC":
        return DOMESTIC_REQUIRED_DOCUMENTS
    elif inbound_source == "FOREIGN":
        return FOREIGN_REQUIRED_DOCUMENTS
    return {}


def latest_documents(documents: list[Document]) -> list[Document]:
    """Keep original versions on disk; use the newest version of each named file."""
    latest: dict[str, Document] = {}
    for doc in documents:
        key = doc.original_filename.casefold()
        previous = latest.get(key)
        if previous is None or (doc.version or 1, doc.uploaded_at) > (previous.version or 1, previous.uploaded_at):
            latest[key] = doc
    return list(latest.values())


def invalidate_approval(shipment) -> None:
    if shipment is not None:
        if shipment.status == "TRANSMITTED":
            from fastapi import HTTPException
            raise HTTPException(409, "Lô hàng đã truyền WMS. Hãy tạo hồ sơ mới để điều chỉnh, tránh lệch với phiếu đã nhận.")
        shipment.approval_status = "PENDING"
        shipment.approved_by = None
        shipment.approved_at = None
        shipment.status = "DRAFT"
