from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from app.db.session import get_db
from app.models.shipment import Shipment
from app.models.document import Document
from app.models.validation import Discrepancy
from app.schemas.shipment import (
    ShipmentCreate,
    ShipmentResponse,
    ShipmentUpdate,
    ShipmentStatsResponse,
    ConsolidatedShipmentHeader,
    FieldProvenance,
)

router = APIRouter(prefix="/shipments", tags=["Shipments"])


def enrich_shipment_response(shipment: Shipment) -> ShipmentResponse:
    res = ShipmentResponse.model_validate(shipment)
    res.document_count = len(shipment.documents) if shipment.documents else 0
    res.discrepancy_count = len(shipment.discrepancies) if shipment.discrepancies else 0
    res.requires_classification = shipment.inbound_source is None
    return res


@router.post("/", response_model=ShipmentResponse, status_code=status.HTTP_201_CREATED)
def create_shipment(payload: ShipmentCreate, db: Session = Depends(get_db)):
    """Tạo mới một lô hàng kho ngoại quan."""
    from app.core.config import settings
    if settings.DEMO_ONLY and db.query(Shipment).count() >= 100:
        raise HTTPException(429, "Bản demo đã đủ 100 hồ sơ. Vui lòng dùng hồ sơ mẫu hiện có.")
    code = payload.shipment_code
    if not code:
        # Auto-generate format SHP-YYYYMMDD-XXXX
        import random
        from datetime import datetime
        date_str = datetime.now().strftime("%Y%m%d")
        rand_suffix = f"{random.randint(1000, 9999)}"
        code = f"SHP-{date_str}-{rand_suffix}"
        # Ensure unique
        while db.query(Shipment).filter(Shipment.shipment_code == code).first():
            rand_suffix = f"{random.randint(1000, 9999)}"
            code = f"SHP-{date_str}-{rand_suffix}"
    else:
        existing = db.query(Shipment).filter(Shipment.shipment_code == code).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Mã lô hàng '{code}' đã tồn tại trong hệ thống."
            )

    data = payload.model_dump()
    data["shipment_code"] = code
    shipment = Shipment(**data)
    db.add(shipment)
    db.commit()
    db.refresh(shipment)
    return enrich_shipment_response(shipment)


@router.get("/statistics/summary", response_model=ShipmentStatsResponse)
def get_shipment_statistics(db: Session = Depends(get_db)):
    """Tổng hợp số liệu thống kê dashboard kho ngoại quan."""
    total = db.query(Shipment).count()
    draft = db.query(Shipment).filter(Shipment.status == "DRAFT").count()
    reconciling = db.query(Shipment).filter(Shipment.status == "RECONCILING").count()
    discrepant = db.query(Shipment).filter(Shipment.status == "DISCREPANT").count()
    validated = db.query(Shipment).filter(Shipment.status == "VALIDATED").count()
    approved = db.query(Shipment).filter(Shipment.status == "APPROVED").count()
    transmitted = db.query(Shipment).filter(Shipment.status == "TRANSMITTED").count()
    inbound = db.query(Shipment).filter(Shipment.direction == "INBOUND").count()
    outbound = db.query(Shipment).filter(Shipment.direction == "OUTBOUND").count()

    return ShipmentStatsResponse(
        total_shipments=total,
        draft_count=draft,
        reconciling_count=reconciling,
        discrepant_count=discrepant,
        validated_count=validated,
        approved_count=approved,
        transmitted_count=transmitted,
        inbound_count=inbound,
        outbound_count=outbound,
    )


@router.get("/", response_model=List[ShipmentResponse])
def list_shipments(
    search: Optional[str] = Query(None, description="Tìm kiếm theo mã lô hàng hoặc số tờ khai"),
    status: Optional[str] = Query(None, description="Lọc theo trạng thái"),
    direction: Optional[str] = Query(None, description="Lọc theo hướng: INBOUND hoặc OUTBOUND"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Danh sách lô hàng kho ngoại quan với tìm kiếm và phân trang."""
    query = db.query(Shipment)

    if search:
        search_filter = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Shipment.shipment_code.ilike(search_filter),
                Shipment.customs_declaration_no.ilike(search_filter),
                Shipment.partner_name.ilike(search_filter),
            )
        )

    if status and status != "ALL":
        query = query.filter(Shipment.status == status)

    if direction and direction != "ALL":
        query = query.filter(Shipment.direction == direction)

    shipments = query.order_by(Shipment.created_at.desc()).offset(skip).limit(limit).all()
    return [enrich_shipment_response(s) for s in shipments]


@router.get("/{shipment_id}", response_model=ShipmentResponse)
def get_shipment(shipment_id: str, db: Session = Depends(get_db)):
    """Lấy thông tin chi tiết một lô hàng."""
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lô hàng.")
    return enrich_shipment_response(shipment)


@router.patch("/{shipment_id}", response_model=ShipmentResponse)
def update_shipment(shipment_id: str, payload: ShipmentUpdate, db: Session = Depends(get_db)):
    """Cập nhật thông tin lô hàng."""
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lô hàng.")
    
    from app.services.validation.documents import invalidate_approval
    from app.services.validation.reconciler import reconciliation_engine
    from app.models.audit import AuditLog

    invalidate_approval(shipment)
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        old_val = getattr(shipment, field)
        if str(old_val) != str(value):
            audit = AuditLog(
                shipment_id=shipment.id,
                action="FIELD_OVERRIDE",
                target_entity="Shipment",
                target_id=shipment.id,
                field_name=field,
                old_value=str(old_val) if old_val is not None else None,
                new_value=str(value) if value is not None else None,
                reason="Nhân viên cập nhật thông tin lô hàng"
            )
            db.add(audit)
        setattr(shipment, field, value)
        
    db.commit()
    db.refresh(shipment)
    # Trigger dynamic revalidation after changes
    reconciliation_engine.reconcile_shipment(db, shipment.id, trigger_reason="Shipment fields updated")
    db.refresh(shipment)
    return enrich_shipment_response(shipment)


@router.delete("/{shipment_id}", status_code=status.HTTP_200_OK)
def delete_shipment(shipment_id: str, db: Session = Depends(get_db)):
    """Xóa lô hàng và dọn sạch các tệp chứng từ đính kèm trên ổ đĩa."""
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lô hàng.")

    # Xóa các tệp chứng từ vật lý trên đĩa
    from app.services.document_parser.storage import storage_service
    from app.models.validation import Discrepancy
    from app.models.audit import AuditLog
    from app.models.wms import WMSReceipt

    for doc in shipment.documents:
        try:
            abs_path = storage_service.get_absolute_path(doc.storage_path)
            if abs_path.exists():
                abs_path.unlink(missing_ok=True)
        except Exception:
            pass

    # Xóa các bản ghi liên quan có khóa ngoại trỏ tới shipment
    db.query(Discrepancy).filter(Discrepancy.shipment_id == shipment_id).delete(synchronize_session=False)
    db.query(AuditLog).filter(AuditLog.shipment_id == shipment_id).delete(synchronize_session=False)
    
    # Xóa WMSReceipts và các line items liên quan
    receipts = db.query(WMSReceipt).filter(WMSReceipt.shipment_id == shipment_id).all()
    for r in receipts:
        db.delete(r)

    code = shipment.shipment_code
    db.delete(shipment)
    db.commit()
    return {"success": True, "message": f"Đã xóa thành công lô hàng {code} và toàn bộ chứng từ liên quan."}


@router.get("/{shipment_id}/consolidated-header", response_model=ConsolidatedShipmentHeader)
def get_consolidated_header(shipment_id: str, db: Session = Depends(get_db)):
    """
    Tổng hợp toàn bộ thông tin chung & vận chuyển của bộ hồ sơ lô hàng từ tất cả các chứng từ thành phần.
    Kèm theo nhãn nguồn gốc (provenance) dẫn xuất đến từng chứng từ cụ thể và ma trận giá trị theo từng chứng từ.
    """
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lô hàng.")

    import json

    def make_prov(val, doc):
        if val is None or val == "":
            return None
        return FieldProvenance(
            value=str(val),
            source_document_name=doc.original_filename if doc else None,
            source_document_type=doc.document_type if doc else None,
            source_document_id=doc.id if doc else None,
        )

    # Initialize empty slots
    customs_dec = None
    dec_type = None
    dec_date = None
    bl_no = None
    ci_no = None
    inv_date = None
    pl_no = None
    shipper = None
    consignee = None
    supplier_name = None
    warehouse_name = None
    vessel_voyage = None
    total_packages = None
    package_unit = None
    gross_weight = None
    net_weight = None
    measurement_cbm = None
    total_inv_val = None
    currency = None
    incoterms = None
    eta = None
    commodity_desc = None
    contract_no = None
    tenant_name = None
    lessor_name = None
    valid_from = None
    valid_until = None
    port_of_discharge = None

    all_containers = []
    all_seals = []
    po_set = set()

    # Per-document values dictionary for side-by-side display
    document_values: dict = {
        "gross_weight": {},
        "packages": {},
        "package_unit": {},
        "cbm": {},
        "containers": {},
        "seals": {},
        "owner": {},
        "supplier": {},
        "vessel_voyage": {},
        "declaration_no": {},
        "eta": {},
        "contract": {},
    }

    for doc in shipment.documents:
        # Collect PO from line items if available
        if doc.extraction and doc.extraction.line_items:
            for li in doc.extraction.line_items:
                if li.po_reference:
                    po_set.add(li.po_reference.strip())
                if not commodity_desc and li.description_vi:
                    commodity_desc = make_prov(li.description_vi, doc)

        if not doc.extraction or not doc.extraction.extracted_header_json:
            continue

        try:
            h = json.loads(doc.extraction.extracted_header_json)
        except Exception:
            continue

        dtype = doc.document_type or h.get("document_type_detected")
        doc_label = doc.original_filename

        for po_val in (h.get("po_numbers") or []):
            if po_val and str(po_val).strip():
                for part in str(po_val).replace(",", " ").replace(";", " ").replace("/", " ").split():
                    p_clean = part.strip().upper()
                    if p_clean and not (len(p_clean) >= 11 and p_clean.isdigit() and p_clean.startswith("20")):
                        po_set.add(p_clean)

        if dtype == "CUSTOMS_DECLARATION" and h.get("port_of_discharge"):
            port_of_discharge = make_prov(h["port_of_discharge"], doc)
        elif h.get("port_of_discharge") and not port_of_discharge:
            port_of_discharge = make_prov(h["port_of_discharge"], doc)

        # Collect containers & seals from all documents
        c_list = h.get("container_numbers") or []
        doc_cnts = []
        for c in c_list:
            if c and str(c).strip():
                c_clean = str(c).strip().upper()
                doc_cnts.append(c_clean)
                if c_clean not in all_containers:
                    all_containers.append(c_clean)
        if doc_cnts:
            document_values["containers"][doc_label] = doc_cnts

        s_list = h.get("seal_numbers") or []
        doc_seals = []
        for s in s_list:
            if s and str(s).strip():
                s_clean = str(s).strip().upper()
                doc_seals.append(s_clean)
                if s_clean not in all_seals:
                    all_seals.append(s_clean)
        if doc_seals:
            document_values["seals"][doc_label] = doc_seals

        # Document specific mappings
        if h.get("total_gross_weight_kg") is not None:
            gw = float(h["total_gross_weight_kg"])
            document_values["gross_weight"][doc_label] = gw
            if not gross_weight:
                gross_weight = make_prov(f"{gw:,.2f}".rstrip('0').rstrip('.') + " kg", doc)

        if h.get("total_packages") is not None:
            pkg = int(h["total_packages"])
            if dtype == "CUSTOMS_DECLARATION" and doc.extraction and doc.extraction.line_items:
                items_sum = sum(int(it.quantity) for it in doc.extraction.line_items if it.quantity and it.quantity > 0)
                p_unit = (h.get("package_unit") or "").strip().upper()
                if items_sum > 0 and (p_unit in ("CT", "CONT", "CONTAINER") or pkg < 10 <= items_sum):
                    pkg = items_sum
            document_values["packages"][doc_label] = pkg
            if not total_packages:
                total_packages = make_prov(f"{pkg}", doc)

        if h.get("package_unit"):
            pu = str(h["package_unit"])
            if dtype == "CUSTOMS_DECLARATION" and pu.strip().upper() in ("CT", "CONT", "CONTAINER") and doc.extraction and doc.extraction.line_items:
                pass
            else:
                document_values["package_unit"][doc_label] = pu
                if not package_unit:
                    package_unit = make_prov(pu, doc)

        if h.get("measurement_cbm") is not None:
            cbm = float(h["measurement_cbm"])
            document_values["cbm"][doc_label] = cbm
            if not measurement_cbm:
                measurement_cbm = make_prov(f"{cbm:,.2f}".rstrip('0').rstrip('.') + " m³", doc)

        if h.get("eta"):
            eta_val = str(h["eta"])
            document_values["eta"][doc_label] = eta_val
            if not eta:
                eta = make_prov(eta_val, doc)

        if h.get("vessel_voyage"):
            vv = str(h["vessel_voyage"])
            document_values["vessel_voyage"][doc_label] = vv
            if not vessel_voyage:
                vessel_voyage = make_prov(vv, doc)

        # Consignee / Importer (Người nhận hàng / Đại lý kho U&I)
        owner_cand = h.get("consignee") or h.get("consignee_importer")
        if owner_cand and dtype in ("COMMERCIAL_INVOICE", "PACKING_LIST", "CUSTOMS_DECLARATION", "BILL_OF_LADING", "ARRIVAL_NOTICE", "SALE_CONTRACT", "PURCHASE_ORDER"):
            document_values["owner"][doc_label] = str(owner_cand)
            if not consignee:
                consignee = make_prov(owner_cand, doc)
        elif owner_cand and not consignee and dtype not in ("WAREHOUSE_CONTRACT",):
            consignee = make_prov(owner_cand, doc)

        # Exporter / Seller / Warehouse Tenant (Người xuất khẩu / Chủ hàng / Bên thuê kho)
        supplier_cand = h.get("shipper") or h.get("shipper_exporter") or h.get("seller_name")
        if dtype == "WAREHOUSE_CONTRACT" and h.get("tenant_name"):
            supplier_cand = h.get("tenant_name")
        elif dtype in ("SALE_CONTRACT", "PURCHASE_ORDER") and h.get("buyer_name"):
            supplier_cand = h.get("buyer_name")

        if supplier_cand and dtype in ("COMMERCIAL_INVOICE", "PACKING_LIST", "CUSTOMS_DECLARATION", "WAREHOUSE_CONTRACT", "SALE_CONTRACT", "PURCHASE_ORDER"):
            document_values["supplier"][doc_label] = str(supplier_cand)
            if not shipper:
                shipper = make_prov(supplier_cand, doc)
            if not supplier_name:
                supplier_name = make_prov(supplier_cand, doc)
        elif supplier_cand and not shipper:
            shipper = make_prov(supplier_cand, doc)

        if h.get("commodity_description") or h.get("goods_description"):
            cd = h.get("commodity_description") or h.get("goods_description")
            if not commodity_desc:
                commodity_desc = make_prov(cd, doc)

        if dtype == "CUSTOMS_DECLARATION":
            if h.get("document_number"):
                customs_dec = make_prov(h["document_number"], doc)
                document_values["declaration_no"][doc_label] = str(h["document_number"])
            if not dec_date and h.get("issue_date"):
                dec_date = make_prov(h["issue_date"], doc)
            if not warehouse_name and h.get("warehouse_name"):
                warehouse_name = make_prov(h["warehouse_name"], doc)
            if not incoterms and h.get("incoterms"):
                incoterms = make_prov(h["incoterms"], doc)
            if not currency and h.get("currency"):
                currency = make_prov(h["currency"], doc)
            if not net_weight and h.get("total_net_weight_kg"):
                nw_val = h['total_net_weight_kg']
                net_weight = make_prov(f"{nw_val:,.2f}".rstrip('0').rstrip('.') + " kg" if isinstance(nw_val, (int, float)) else f"{nw_val} kg", doc)

        elif dtype == "BILL_OF_LADING":
            if not bl_no and h.get("document_number"):
                bl_no = make_prov(h["document_number"], doc)

        elif dtype == "COMMERCIAL_INVOICE":
            if not ci_no and h.get("document_number"):
                ci_no = make_prov(h["document_number"], doc)
            if not inv_date and h.get("issue_date"):
                inv_date = make_prov(h["issue_date"], doc)
            if not total_inv_val and h.get("total_invoice_value") is not None:
                curr_sym = h.get("currency") or "USD"
                inv_val = h['total_invoice_value']
                val_str = f"{inv_val:,.2f}".rstrip('0').rstrip('.') if isinstance(inv_val, (int, float)) else str(inv_val)
                total_inv_val = make_prov(f"{val_str} {curr_sym}", doc)
            if not currency and h.get("currency"):
                currency = make_prov(h["currency"], doc)
            if not incoterms and h.get("incoterms"):
                incoterms = make_prov(h["incoterms"], doc)

        elif dtype == "PACKING_LIST":
            if not pl_no and h.get("document_number"):
                pl_no = make_prov(h["document_number"], doc)
            if not net_weight and h.get("total_net_weight_kg"):
                nw_val = h['total_net_weight_kg']
                net_weight = make_prov(f"{nw_val:,.2f}".rstrip('0').rstrip('.') + " kg" if isinstance(nw_val, (int, float)) else f"{nw_val} kg", doc)

        elif dtype == "WAREHOUSE_CONTRACT":
            if h.get("document_number"):
                contract_no = make_prov(h["document_number"], doc)
            if h.get("tenant_name"):
                tenant_name = make_prov(h["tenant_name"], doc)
            if h.get("lessor_name"):
                lessor_name = make_prov(h["lessor_name"], doc)
            if h.get("valid_from"):
                valid_from = make_prov(h["valid_from"], doc)
            if h.get("valid_until"):
                valid_until = make_prov(h["valid_until"], doc)
            document_values["contract"][doc_label] = {
                "document_number": h.get("document_number"),
                "tenant_name": h.get("tenant_name"),
                "lessor_name": h.get("lessor_name"),
                "valid_from": h.get("valid_from"),
                "valid_until": h.get("valid_until"),
            }

        elif dtype in ("PURCHASE_ORDER", "SALE_CONTRACT"):
            if h.get("document_number"):
                po_set.add(str(h["document_number"]).strip())

    # Fallbacks from Shipment entity
    if not customs_dec and shipment.customs_declaration_no:
        customs_dec = FieldProvenance(
            value=shipment.customs_declaration_no,
            source_document_name="Lô hàng kho ngoại quan",
            source_document_type="CUSTOMS_DECLARATION"
        )
    if shipment.declaration_type:
        dec_type = FieldProvenance(
            value=shipment.declaration_type,
            source_document_name="Lô hàng kho ngoại quan",
            source_document_type="CUSTOMS_DECLARATION"
        )
    if not warehouse_name and shipment.bonded_warehouse_name:
        warehouse_name = FieldProvenance(
            value=shipment.bonded_warehouse_name,
            source_document_name="Lô hàng kho ngoại quan",
            source_document_type="CUSTOMS_DECLARATION"
        )
    if not consignee and shipment.partner_name and shipment.direction == "INBOUND":
        consignee = FieldProvenance(
            value=shipment.partner_name,
            source_document_name="Lô hàng kho ngoại quan",
            source_document_type="CUSTOMS_DECLARATION"
        )

    from app.services.validation.documents import latest_documents
    from app.services.validation.matrix import evaluate_cross_document_matrix
    matrix_rows, _, has_sc = evaluate_cross_document_matrix(latest_documents(shipment.documents), shipment)

    return ConsolidatedShipmentHeader(
        shipment_id=shipment.id,
        shipment_code=shipment.shipment_code,
        status=shipment.status,
        approval_status=shipment.approval_status,
        inbound_source=shipment.inbound_source,
        requires_classification=shipment.inbound_source is None,
        entry_date=shipment.entry_date.isoformat() if shipment.entry_date else None,
        eta=eta,
        supplier_name=supplier_name,
        commodity_description=commodity_desc,
        package_unit=package_unit,
        measurement_cbm=measurement_cbm,
        contract_no=contract_no,
        tenant_name=tenant_name,
        lessor_name=lessor_name,
        valid_from=valid_from,
        valid_until=valid_until,
        customs_declaration_no=customs_dec,
        declaration_type=dec_type,
        declaration_date=dec_date,
        bill_of_lading_no=bl_no,
        commercial_invoice_no=ci_no,
        invoice_date=inv_date,
        packing_list_no=pl_no,
        po_numbers=sorted(list(po_set)),
        shipper=shipper,
        consignee=consignee,
        warehouse_name=warehouse_name,
        vessel_voyage=vessel_voyage,
        port_of_discharge=port_of_discharge,
        container_numbers=all_containers,
        seal_numbers=all_seals,
        total_packages=total_packages,
        total_gross_weight_kg=gross_weight,
        total_net_weight_kg=net_weight,
        total_invoice_value=total_inv_val,
        currency=currency,
        incoterms=incoterms,
        document_values=document_values,
        field_matrix=matrix_rows,
        has_sale_contract=has_sc,
    )

@router.post("/sync/import-local-data")
def import_local_data(payload: dict, db: Session = Depends(get_db)):
    """Import local database records and uploaded files onto remote server."""
    import base64
    from pathlib import Path
    from app.core.config import settings
    from app.models.shipment import Shipment
    from app.models.document import Document
    from app.models.document_extraction import DocumentExtraction
    from app.models.extraction import ExtractedLineItem
    from app.models.validation import Discrepancy, ValidationRuleSetting
    from app.models.audit import AuditLog
    from datetime import datetime, date

    files_dict = payload.get("files", {})
    # Save files to uploads directory
    target_dir = settings.UPLOAD_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    for fn, b64_content in files_dict.items():
        try:
            file_bytes = base64.b64decode(b64_content)
            target_file = target_dir / fn
            with open(target_file, "wb") as f:
                f.write(file_bytes)
        except Exception:
            pass

    # Helper date parser
    def parse_dt(v):
        if not v:
            return None
        try:
            return datetime.fromisoformat(v)
        except Exception:
            return None

    def parse_d(v):
        if not v:
            return None
        try:
            return date.fromisoformat(v)
        except Exception:
            return None

    # Clear old data to avoid duplicate PK errors
    db.query(ExtractedLineItem).delete()
    db.query(DocumentExtraction).delete()
    db.query(Discrepancy).delete()
    db.query(AuditLog).delete()
    db.query(Document).delete()
    db.query(Shipment).delete()
    db.flush()

    # Import shipments
    for s_data in payload.get("shipments", []):
        s = Shipment(
            id=s_data["id"],
            shipment_code=s_data["shipment_code"],
            customs_declaration_no=s_data.get("customs_declaration_no"),
            declaration_type=s_data.get("declaration_type"),
            warehouse_type=s_data.get("warehouse_type", "BONDED"),
            bonded_warehouse_name=s_data.get("bonded_warehouse_name"),
            partner_name=s_data.get("partner_name"),
            direction=s_data.get("direction", "INBOUND"),
            inbound_source=s_data.get("inbound_source"),
            status=s_data.get("status", "DRAFT"),
            approval_status=s_data.get("approval_status", "PENDING"),
            approved_by=s_data.get("approved_by"),
            approved_at=parse_dt(s_data.get("approved_at")),
            entry_date=parse_d(s_data.get("entry_date")),
            notes=s_data.get("notes"),
            created_at=parse_dt(s_data.get("created_at")) or datetime.utcnow(),
            updated_at=parse_dt(s_data.get("updated_at")) or datetime.utcnow()
        )
        db.add(s)
    db.flush()

    # Import documents
    for d_data in payload.get("documents", []):
        fn = Path(d_data["storage_path"]).name
        actual_path = str((target_dir / fn).resolve()).replace("\\", "/")
        d = Document(
            id=d_data["id"],
            shipment_id=d_data["shipment_id"],
            original_filename=d_data["original_filename"],
            storage_path=actual_path,
            mime_type=d_data["mime_type"],
            sha256_hash=d_data["sha256_hash"],
            file_size_bytes=d_data["file_size_bytes"],
            page_count=d_data.get("page_count"),
            document_type=d_data.get("document_type"),
            parsed_content_json=d_data.get("parsed_content_json"),
            version=d_data.get("version", 1),
            uploaded_at=parse_dt(d_data.get("uploaded_at")) or datetime.utcnow()
        )
        db.add(d)
    db.flush()

    # Import document_extractions
    for e_data in payload.get("document_extractions", []):
        e = DocumentExtraction(
            id=e_data["id"],
            document_id=e_data["document_id"],
            status=e_data.get("status", "SUCCESS"),
            model_name=e_data.get("model_name"),
            raw_response_json=e_data.get("raw_response_json"),
            confidence_score=e_data.get("confidence_score"),
            error_message=e_data.get("error_message"),
            extracted_header_json=e_data.get("extracted_header_json"),
            extracted_at=parse_dt(e_data.get("extracted_at")) or datetime.utcnow(),
            version=e_data.get("version", 1),
            prompt_tokens=e_data.get("prompt_tokens"),
            candidate_tokens=e_data.get("candidate_tokens")
        )
        db.add(e)
    db.flush()

    # Import extracted_line_items
    for it_data in payload.get("extracted_line_items", []):
        it = ExtractedLineItem(
            id=it_data["id"],
            extraction_id=it_data["extraction_id"],
            item_index=it_data.get("item_index", 1),
            sku=it_data.get("sku"),
            part_number=it_data.get("part_number"),
            description_vi=it_data.get("description_vi"),
            hs_code=it_data.get("hs_code"),
            quantity=it_data.get("quantity"),
            uom=it_data.get("uom"),
            unit_price=it_data.get("unit_price"),
            total_amount=it_data.get("total_amount"),
            currency=it_data.get("currency"),
            gross_weight_kg=it_data.get("gross_weight_kg"),
            net_weight_kg=it_data.get("net_weight_kg"),
            po_reference=it_data.get("po_reference"),
            page_number=it_data.get("page_number"),
            raw_line_text=it_data.get("raw_line_text"),
            bounding_box_json=it_data.get("bounding_box_json")
        )
        db.add(it)
    db.flush()

    # Import discrepancies
    for disc_data in payload.get("discrepancies", []):
        disc = Discrepancy(
            id=disc_data["id"],
            shipment_id=disc_data["shipment_id"],
            rule_code=disc_data["rule_code"],
            severity=disc_data["severity"],
            field_name=disc_data["field_name"],
            description_vi=disc_data["description_vi"],
            category=disc_data.get("category", "CONFLICT"),
            source_doc_a_id=disc_data.get("source_doc_a_id"),
            source_doc_a_name=disc_data.get("source_doc_a_name"),
            value_a=disc_data.get("value_a"),
            source_doc_b_id=disc_data.get("source_doc_b_id"),
            source_doc_b_name=disc_data.get("source_doc_b_name"),
            value_b=disc_data.get("value_b"),
            status=disc_data.get("status", "OPEN"),
            resolution_action=disc_data.get("resolution_action"),
            resolution_reason=disc_data.get("resolution_reason"),
            resolved_by=disc_data.get("resolved_by"),
            resolved_at=parse_dt(disc_data.get("resolved_at")),
            created_at=parse_dt(disc_data.get("created_at")) or datetime.utcnow(),
            updated_at=parse_dt(disc_data.get("updated_at")) or datetime.utcnow()
        )
        db.add(disc)

    db.commit()
    return {
        "success": True,
        "imported_shipments": len(payload.get("shipments", [])),
        "imported_documents": len(payload.get("documents", [])),
        "imported_files": len(files_dict)
    }

