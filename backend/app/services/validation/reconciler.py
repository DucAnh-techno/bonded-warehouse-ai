import json
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.shipment import Shipment
from app.models.document import Document
from app.models.validation import Discrepancy
from app.models.audit import AuditLog
from app.services.validation.contract import validate_contract
from app.services.validation.documents import latest_documents, get_required_documents, DOMESTIC_REQUIRED_DOCUMENTS, FOREIGN_REQUIRED_DOCUMENTS
from app.services.validation.config import get_rule_map
from app.services.validation.rules import validation_engine, ValidationRuleResult, compute_tolerance_pct
from app.services.validation.matrix import evaluate_cross_document_matrix


class CrossDocumentReconciliationEngine:
    """
    Coordinates Multi-PO and Multi-SKU reconciliation across all documents in a shipment.
    Generates Discrepancy records without ever auto-resolving conflicts.
    Supports dynamic revalidation when corrections are made.
    """

    def reconcile_shipment(
        self,
        db: Session,
        shipment_id: str,
        trigger_reason: str = "INITIAL_RECONCILIATION",
        persist: bool = True
    ) -> Dict[str, Any]:
        shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
        if not shipment:
            raise ValueError(f"Shipment {shipment_id} not found.")

        documents = latest_documents(db.query(Document).filter(Document.shipment_id == shipment_id).all())
        rule_map = get_rule_map(db)

        sku_map: Dict[str, Dict[str, Any]] = {}
        headers_by_type: Dict[str, Dict[str, Any]] = {}

        SKU_RECONCILABLE_DOC_TYPES = {
            "COMMERCIAL_INVOICE",
            "PACKING_LIST",
        }

        NON_SKU_PATTERNS = (
            "DETAILS AS PER BILL OF LADING",
            "SAID TO CONTAIN",
            "AS PER B/L",
            "AS PER BILL OF LADING",
            "CARGO AS PER",
        )

        for doc in documents:
            if not doc.extraction or doc.extraction.status != "SUCCESS":
                continue

            doc_type = doc.document_type
            if doc.extraction.extracted_header_json:
                try:
                    headers_by_type[doc_type] = json.loads(doc.extraction.extracted_header_json)
                except Exception:
                    headers_by_type[doc_type] = {}

            # Vận đơn (B/L), Thông báo hàng đến (Arrival Notice) chỉ quản lý container/seal/trọng lượng,
            # KHÔNG chứa chi tiết mặt hàng SKU và không tham gia đối soát chi tiết dòng hàng.
            if doc_type not in SKU_RECONCILABLE_DOC_TYPES:
                continue

            doc_hdr = headers_by_type.get(doc_type, {})
            doc_header_pos = doc_hdr.get("po_numbers") or []
            fallback_po = str(doc_header_pos[0]).strip().upper() if len(doc_header_pos) == 1 and doc_header_pos[0] else None

            for item in doc.extraction.line_items:
                desc_upper = (item.description_vi or "").upper()
                sku_upper = (item.sku or "").upper()
                if any(pat in desc_upper or pat in sku_upper for pat in NON_SKU_PATTERNS):
                    continue

                raw_po = (item.po_reference or "").strip()
                po_val = raw_po if raw_po and raw_po != "-" else fallback_po
                sku_key = (item.sku or item.part_number or item.description_vi or f"ITEM-{item.item_index}").strip().upper()
                display_sku = sku_key
                sku_key = f"{(po_val or chr(45)).strip().upper()}::{sku_key}"
                if sku_key not in sku_map:
                    sku_map[sku_key] = {
                        "sku": display_sku,
                        "po_reference": po_val or item.po_reference,
                        "description_vi": item.description_vi or sku_key,
                        "uom": item.uom or "Cái",
                        "quantities": {},
                        "unit_prices": {},
                        "hs_codes": {},
                        "line_items": [],
                    }
                elif not sku_map[sku_key]["po_reference"] and po_val:
                    sku_map[sku_key]["po_reference"] = po_val

                if item.quantity is not None:
                    sku_map[sku_key]["quantities"][doc_type] = sku_map[sku_key]["quantities"].get(doc_type, 0) + item.quantity
                if item.unit_price is not None:
                    sku_map[sku_key]["unit_prices"][doc_type] = item.unit_price
                if item.hs_code:
                    sku_map[sku_key]["hs_codes"][doc_type] = item.hs_code
                if item.description_vi and (sku_map[sku_key]["description_vi"] == sku_key or not sku_map[sku_key]["description_vi"]):
                    sku_map[sku_key]["description_vi"] = item.description_vi
                if item.uom:
                    if doc_type == "COMMERCIAL_INVOICE" or not sku_map[sku_key].get("uom") or sku_map[sku_key]["uom"] == "Cái":
                        sku_map[sku_key]["uom"] = item.uom

                sku_map[sku_key]["line_items"].append((doc, item))

        rule_results: List[ValidationRuleResult] = []

        def missing(field, message, source=None, severity="ERROR", category="MISSING"):
            rule_results.append(
                ValidationRuleResult(
                    rule_code="VAL-DATA-001",
                    rule_name_vi="Dữ liệu bắt buộc",
                    passed=False,
                    severity=severity,
                    category=category,
                    field_name=field,
                    description_vi=message,
                    source_doc_a_name=source,
                )
            )

        # 0. VAL-DOC-001: Mandatory Core Documents Check (Domestic: 4, Foreign: 6)
        present_doc_types = [doc.document_type for doc in documents if doc.document_type]
        doc_errs = validation_engine.validate_mandatory_documents(present_doc_types, shipment.inbound_source)
        for err in doc_errs:
            rule_results.append(err)

        required_docs_map = get_required_documents(shipment.inbound_source)
        if not required_docs_map:
            required_docs_map = DOMESTIC_REQUIRED_DOCUMENTS

        owners = []
        exporters: List[str] = []
        consignees: List[str] = []
        all_containers: List[str] = []
        all_seals: List[str] = []
        packages_by_doc: Dict[str, Optional[int]] = {}
        units_by_doc: Dict[str, Optional[str]] = {}
        gross_weights_by_doc: Dict[str, Optional[float]] = {}
        cbms_by_doc: Dict[str, Optional[float]] = {}
        has_commodity_desc = bool(shipment.notes)

        for doc in documents:
            if not doc.extraction or doc.extraction.status != "SUCCESS":
                if doc.document_type in required_docs_map or doc.document_type in ("WAREHOUSE_CONTRACT", "SALE_CONTRACT", "PURCHASE_ORDER"):
                    missing(f"document[{doc.id}].extraction", "Chứng từ chưa trích xuất thành công.", doc.original_filename)
                continue

            hdr = json.loads(doc.extraction.extracted_header_json or "{}")

            # Collect containers & seals
            for c in hdr.get("container_numbers", []):
                if c and str(c).strip() and str(c).strip() not in all_containers:
                    all_containers.append(str(c).strip())
            for s in hdr.get("seal_numbers", []):
                if s and str(s).strip() and str(s).strip() not in all_seals:
                    all_seals.append(str(s).strip())

            # Collect metrics by document
            dtype = doc.document_type or doc.original_filename
            if hdr.get("total_packages") is not None:
                try:
                    pkg_val = int(hdr["total_packages"])
                    # Trên Tờ khai hải quan, nếu số kiện ở header ghi số container (ví dụ: 2 CT / 2 CONT)
                    # thì ưu tiên lấy tổng số lượng kiện từ dòng hàng chi tiết của Tờ khai để khớp với B/L và PL
                    if doc.document_type == "CUSTOMS_DECLARATION" and doc.extraction and doc.extraction.line_items:
                        items_sum = sum(int(it.quantity) for it in doc.extraction.line_items if it.quantity and it.quantity > 0)
                        p_unit = (hdr.get("package_unit") or "").strip().upper()
                        if items_sum > 0 and (p_unit in ("CT", "CONT", "CONTAINER") or pkg_val < 10 <= items_sum):
                            pkg_val = items_sum
                    packages_by_doc[dtype] = pkg_val
                except Exception:
                    pass
            if hdr.get("package_unit"):
                pu = str(hdr["package_unit"]).strip().upper()
                if doc.document_type == "CUSTOMS_DECLARATION" and pu in ("CT", "CONT", "CONTAINER") and doc.extraction and doc.extraction.line_items:
                    # Bỏ qua đơn vị container để không gây lỗi lệch đơn vị đóng gói với carton/kiện của B/L
                    pass
                else:
                    units_by_doc[dtype] = pu

            if hdr.get("total_gross_weight_kg") is not None:
                try:
                    gross_weights_by_doc[dtype] = float(hdr["total_gross_weight_kg"])
                except Exception:
                    pass

            if hdr.get("measurement_cbm") is not None:
                try:
                    cbms_by_doc[dtype] = float(hdr["measurement_cbm"])
                except Exception:
                    pass

            if hdr.get("commodity_description") or hdr.get("goods_description"):
                has_commodity_desc = True

            # Exporters / Cargo owners for contract and customs match
            has_sc_doc = any(
                d.document_type in ("SALE_CONTRACT", "PURCHASE_ORDER") and d.extraction and d.extraction.status == "SUCCESS"
                for d in documents
            )
            if doc.document_type in ("SALE_CONTRACT", "PURCHASE_ORDER"):
                sc_buyer = hdr.get("buyer_name") or hdr.get("cargo_owner_name") or hdr.get("tenant_name")
                if sc_buyer and sc_buyer not in exporters:
                    exporters.append(sc_buyer)
                # Populate PO SKU quantities if SC has line items
                for item in doc.extraction.line_items:
                    raw_s = (item.sku or item.part_number or "").strip().upper()
                    if raw_s and item.quantity is not None:
                        for s_key, s_data in sku_map.items():
                            if s_data["sku"].strip().upper() == raw_s:
                                s_data["quantities"]["PURCHASE_ORDER"] = s_data["quantities"].get("PURCHASE_ORDER", 0) + item.quantity
            elif doc.document_type in ("COMMERCIAL_INVOICE", "PACKING_LIST"):
                if has_sc_doc:
                    # Khi có SC: INV (và PL) là giữa Seller và Buyer (trên SC) ký với nhau -> Chủ hàng là Buyer
                    exp_cand = hdr.get("buyer_name") or hdr.get("cargo_owner_name")
                    if not exp_cand:
                        c_val = hdr.get("consignee") or hdr.get("consignee_importer")
                        if c_val and "U&I" not in str(c_val).upper() and "U & I" not in str(c_val).upper():
                            exp_cand = c_val
                        else:
                            exp_cand = hdr.get("shipper") or hdr.get("shipper_exporter") or hdr.get("seller_name")
                else:
                    # Khi không có SC: INV là giữa U&I và Chủ hàng ký với nhau -> Chủ hàng đứng ở Shipper
                    exp_cand = hdr.get("shipper") or hdr.get("shipper_exporter") or hdr.get("seller_name") or hdr.get("exporter_name")
                if exp_cand and exp_cand not in exporters:
                    exporters.append(exp_cand)
            elif doc.document_type == "CUSTOMS_DECLARATION":
                if has_sc_doc:
                    # Khi có SC: Người xuất khẩu trên Tờ khai là Seller trên SC, không phải Chủ hàng thuê kho
                    exp_cand = hdr.get("cargo_owner_name")
                else:
                    exp_cand = hdr.get("shipper") or hdr.get("shipper_exporter") or hdr.get("seller_name") or hdr.get("exporter_name")
                if exp_cand and exp_cand not in exporters:
                    exporters.append(exp_cand)

            # Consignees for U&I check (BL, AN, SC, Invoice [khi không có SC], PL, Customs Declaration)
            if doc.document_type in ("BILL_OF_LADING", "ARRIVAL_NOTICE", "SALE_CONTRACT", "PURCHASE_ORDER", "COMMERCIAL_INVOICE", "PACKING_LIST", "CUSTOMS_DECLARATION"):
                consignee_cand = hdr.get("consignee") or hdr.get("consignee_importer")
                if not consignee_cand and not has_sc_doc and doc.document_type in ("COMMERCIAL_INVOICE", "PACKING_LIST", "CUSTOMS_DECLARATION"):
                    consignee_cand = hdr.get("buyer_name")
                # Khi có SC, trên INV mục người mua có thể là Buyer (Chủ hàng), không đưa Buyer vào consignees đối chiếu với Lessor U&I
                if has_sc_doc and doc.document_type in ("COMMERCIAL_INVOICE", "PACKING_LIST") and consignee_cand and consignee_cand in exporters:
                    consignee_cand = None
                if consignee_cand and consignee_cand not in consignees:
                    consignees.append(consignee_cand)

            if doc.document_type in ("COMMERCIAL_INVOICE", "PACKING_LIST"):
                if not doc.extraction.line_items:
                    missing(f"document[{doc.id}].items", "Chứng từ chưa có dòng hàng.", doc.original_filename)
                for item in doc.extraction.line_items:
                    if item.description_vi:
                        has_commodity_desc = True
                    if not (item.sku or item.part_number or item.description_vi) or not item.uom or item.quantity is None or item.quantity <= 0:
                        missing(f"item[{item.id}]", "Tên hàng/SKU, đơn vị tính và số lượng dương là bắt buộc.", doc.original_filename)
                    if doc.document_type == "COMMERCIAL_INVOICE" and (item.unit_price is None or item.total_amount is None):
                        missing(f"item[{item.id}].price", "Thiếu đơn giá hoặc thành tiền Invoice.", doc.original_filename)

        if shipment.partner_name and shipment.partner_name not in exporters:
            exporters.append(shipment.partner_name)

        # Validate Warehouse Contract:
        # - Bên thuê kho (Tenant) = Chủ hàng (Buyer ở SC / Shipper ở Invoice-PL / XK ở Tờ khai khi không có SC)
        # - Người nhận (Consignee) = U&I
        for doc in documents:
            if doc.document_type == "WAREHOUSE_CONTRACT" and doc.extraction and doc.extraction.status == "SUCCESS":
                rule_results.extend(
                    validate_contract(
                        json.loads(doc.extraction.extracted_header_json or "{}"),
                        shipment.entry_date,
                        exporters,
                        consignees,
                        doc.original_filename
                    )
                )

        # Validate mandatory container numbers (Container is mandatory for all shipments)
        cnt_err = validation_engine.validate_mandatory_containers(all_containers)
        if cnt_err:
            rule_results.append(cnt_err)

        # Validate mandatory customs declaration number
        dec_no = shipment.customs_declaration_no
        if not dec_no:
            for doc in documents:
                if doc.document_type == "CUSTOMS_DECLARATION" and doc.extraction:
                    hdr_dec = json.loads(doc.extraction.extracted_header_json or "{}")
                    if hdr_dec.get("document_number"):
                        dec_no = hdr_dec["document_number"]
                        break
        dec_err = validation_engine.validate_mandatory_customs_declaration(dec_no)
        if dec_err:
            rule_results.append(dec_err)

        # Validate mandatory cargo owner (Consignee hoặc Exporter)
        if not consignees and not exporters:
            missing("shipment.cargo_owner", "Thiếu thông tin chủ hàng (Consignee/Buyer) trên toàn bộ hồ sơ.")

        # Validate mandatory actual arrival date
        if not shipment.entry_date:
            missing("shipment.entry_date", "Thiếu thời gian hàng đến thực tế (Actual Arrival Date) do nhân viên nhập hoặc xác nhận; không tự dùng ETA thay thế.")

        # Validate mandatory commodity description
        if not has_commodity_desc:
            missing("shipment.commodity_description", "Thiếu chủng loại / mô tả hàng hóa trên toàn bộ hồ sơ.")

        # Validate packages count
        if not packages_by_doc:
            missing("shipment.total_packages", "Thiếu tổng số lượng kiện hàng trên toàn bộ hồ sơ.")
        else:
            rule_results.extend(validation_engine.validate_package_counts(packages_by_doc, units_by_doc))
            if len(packages_by_doc) == 1:
                missing(
                    "shipment.total_packages_single_source",
                    f"Chỉ có một nguồn cung cấp số kiện ({next(iter(packages_by_doc.keys()))}: {next(iter(packages_by_doc.values()))} kiện). Chưa đủ nguồn đối chiếu chéo.",
                    source=next(iter(packages_by_doc.keys())),
                    severity="INFO",
                    category="NOT_VERIFIED"
                )

        # Validate gross weight
        if not gross_weights_by_doc:
            missing("shipment.total_gross_weight_kg", "Thiếu thông tin tổng trọng lượng cả bì (Gross Weight) trên toàn bộ hồ sơ.")
        else:
            gw_keys = list(gross_weights_by_doc.keys())
            for i in range(len(gw_keys)):
                for j in range(i + 1, len(gw_keys)):
                    k1, k2 = gw_keys[i], gw_keys[j]
                    w_err = validation_engine.validate_weight_tolerance(
                        gross_weights_by_doc[k1], gross_weights_by_doc[k2], k1, k2, tolerance_pct=0.5
                    )
                    if w_err:
                        rule_results.append(w_err)
            if len(gross_weights_by_doc) == 1:
                missing(
                    "shipment.gross_weight_single_source",
                    f"Chỉ có một nguồn cung cấp Gross Weight ({gw_keys[0]}: {gross_weights_by_doc[gw_keys[0]]:,.2f} kg). Chưa đủ nguồn đối chiếu chéo.",
                    source=gw_keys[0],
                    severity="INFO",
                    category="NOT_VERIFIED"
                )

        # Validate CBM if available
        if cbms_by_doc:
            cbm_keys = list(cbms_by_doc.keys())
            if len(cbm_keys) >= 2:
                for i in range(len(cbm_keys)):
                    for j in range(i + 1, len(cbm_keys)):
                        k1, k2 = cbm_keys[i], cbm_keys[j]
                        c_err = validation_engine.validate_cbm_tolerance(
                            cbms_by_doc[k1], cbms_by_doc[k2], k1, k2, tolerance_pct=0.5
                        )
                        if c_err:
                            rule_results.append(c_err)
            else:
                missing(
                    "shipment.cbm_single_source",
                    f"Chỉ có một nguồn cung cấp thể tích CBM ({cbm_keys[0]}: {cbms_by_doc[cbm_keys[0]]:,.2f} m³). Chưa đủ nguồn đối chiếu chéo.",
                    source=cbm_keys[0],
                    severity="INFO",
                    category="NOT_VERIFIED"
                )

        # Seals warning if missing
        if not all_seals:
            missing(
                "shipment.seal_numbers",
                "Hồ sơ chưa có số chì niêm phong (Seal). Cần kiểm tra niêm phong thực tế khi nhập kho.",
                severity="WARNING",
                category="MISSING"
            )

        # 1. VAL-PRC-001: Line item arithmetic on Invoice / Declaration
        tol_prc = 0.01
        for sku_key, data in sku_map.items():
            for doc, item in data["line_items"]:
                if item.quantity is None:
                    continue
                res_math = validation_engine.validate_line_item_math(
                    item_index=item.item_index,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    total_amount=item.total_amount,
                    tolerance=tol_prc
                )
                if res_math:
                    res_math.severity = "ERROR"
                    res_math.source_doc_a_name = doc.original_filename
                    rule_results.append(res_math)

        # 2. VAL-HS-001: HS Code Format Check
        rule_hs = rule_map.get("VAL-HS-001")
        if rule_hs and rule_hs.enabled:
            for sku_key, data in sku_map.items():
                hs_code = next(iter(data["hs_codes"].values()), None)
                res_hs = validation_engine.validate_hs_code_format(sku=sku_key, hs_code=hs_code)
                if res_hs and hs_code:
                    res_hs.severity = rule_hs.severity
                    rule_results.append(res_hs)

        # 3. VAL-HS-002: Cross-document HS Code Consistency (Declaration vs Commercial Invoice)
        rule_hs_match = rule_map.get("VAL-HS-002")
        dec_hs_by_sku: Dict[str, str] = {}
        for doc in documents:
            if doc.document_type == "CUSTOMS_DECLARATION" and doc.extraction and doc.extraction.status == "SUCCESS":
                for item in doc.extraction.line_items:
                    raw_s = (item.sku or item.part_number or "").strip().upper()
                    if raw_s:
                        if item.hs_code:
                            dec_hs_by_sku[raw_s] = item.hs_code
                        # Populate qty_declaration for matching SKU if available
                        for sku_key, data in sku_map.items():
                            if data["sku"].strip().upper() == raw_s:
                                if item.quantity is not None:
                                    data["quantities"]["CUSTOMS_DECLARATION"] = data["quantities"].get("CUSTOMS_DECLARATION", 0) + item.quantity
                                if item.hs_code:
                                    data["hs_codes"]["CUSTOMS_DECLARATION"] = item.hs_code

        if rule_hs_match and rule_hs_match.enabled:
            for sku_key, data in sku_map.items():
                raw_sku = data.get("sku", "").strip().upper()
                hs_dec = dec_hs_by_sku.get(raw_sku) or data["hs_codes"].get("CUSTOMS_DECLARATION")
                hs_ci = data["hs_codes"].get("COMMERCIAL_INVOICE")
                if hs_dec and hs_ci:
                    res_hsm = validation_engine.validate_hs_code_match(sku=sku_key, hs_declaration=hs_dec, hs_invoice=hs_ci)
                    if res_hsm:
                        res_hsm.severity = rule_hs_match.severity
                        rule_results.append(res_hsm)

        def _norm_item_uom(u: str) -> str:
            s = u.strip().upper()
            if s in ("PC", "PCS", "PCE", "PIECE", "PIECES", "CAI", "CÁI", "CHIẾC", "CHIEC", "UNIT", "UNITS", "EA", "EACH"):
                return "PIECE"
            if s in ("CT", "CTN", "CTNS", "CARTON", "CARTONS", "THUNG", "THÙNG"):
                return "CARTON"
            if s in ("PL", "PLT", "PLTS", "PALLET", "PALLETS"):
                return "PALLET"
            if s in ("PKG", "PKGS", "PACKAGE", "PACKAGES", "KIEN", "KIỆN"):
                return "PACKAGE"
            if s in ("SET", "SETS", "BO", "BỘ"):
                return "SET"
            if s in ("BOX", "BOXES", "HOP", "HỘP"):
                return "BOX"
            if s in ("KG", "KGS", "KGM", "KILOGRAM", "KILOGRAMS"):
                return "KG"
            return s

        # 4. VAL-QTY-001: Cross-document SKU Quantity Triangulation (Invoice vs Packing List)
        for sku_key, data in sku_map.items():
            q_pl = data["quantities"].get("PACKING_LIST")
            q_ci = data["quantities"].get("COMMERCIAL_INVOICE")
            res_qty = validation_engine.validate_cross_document_quantities(
                sku=sku_key, qty_pl=q_pl, qty_ci=q_ci, qty_dec=None
            )
            if q_pl is None and q_ci is not None:
                missing(f"sku[{sku_key}].quantity", f"Dòng hàng ({sku_key}) có trên Invoice nhưng thiếu trên Packing List.")
            elif q_ci is None and q_pl is not None:
                missing(f"sku[{sku_key}].quantity", f"Dòng hàng ({sku_key}) có trên Packing List nhưng thiếu trên Invoice.")
            raw_units = {item.uom.strip().upper() for _, item in data["line_items"] if item.uom}
            norm_units = {_norm_item_uom(u) for u in raw_units}
            # Nếu SL trên CI và PL khớp nhau hoàn toàn và một bên ghi PIECE (PCS), bên kia ghi CARTON (CTNS) (1 kiện = 1 sản phẩm) thì cho phép khớp
            qty_matched = (q_pl is not None and q_ci is not None and abs(q_pl - q_ci) <= 0.001)
            if len(norm_units) > 1 and not (qty_matched and norm_units == {"PIECE", "CARTON"}):
                missing(f"sku[{sku_key}].quantity", f"Đơn vị tính không khớp ({', '.join(sorted(raw_units))}); không tự quy đổi.")
            if res_qty:
                res_qty.severity = "ERROR"
                rule_results.append(res_qty)

        # Header-level invoice total checks
        for doc in documents:
            if doc.document_type != "COMMERCIAL_INVOICE" or not doc.extraction or doc.extraction.status != "SUCCESS":
                continue
            header = json.loads(doc.extraction.extracted_header_json or "{}")
            declared = header.get("total_invoice_value")
            if declared is None:
                missing(f"document[{doc.id}].total", "Thiếu tổng trị giá Invoice.", doc.original_filename)
            else:
                total = sum(item.total_amount or 0 for item in doc.extraction.line_items)
                finding = validation_engine.validate_invoice_total_sum(declared, total)
                if finding:
                    finding.field_name = f"document[{doc.id}].total"
                    finding.source_doc_a_name = doc.original_filename
                    rule_results.append(finding)

        # Container numbers match across B/L and Declaration
        dec_header = headers_by_type.get("CUSTOMS_DECLARATION", {})
        ci_header = headers_by_type.get("COMMERCIAL_INVOICE", {})
        bl_header = headers_by_type.get("BILL_OF_LADING", {})
        pl_header = headers_by_type.get("PACKING_LIST", {})

        rule_cnt = rule_map.get("VAL-CNT-001")
        if rule_cnt and rule_cnt.enabled:
            containers_dec = dec_header.get("container_numbers", [])
            containers_bl = bl_header.get("container_numbers", [])
            res_cnt = validation_engine.validate_container_numbers(containers_bl, containers_dec)
            if res_cnt:
                res_cnt.severity = rule_cnt.severity
                rule_results.append(res_cnt)

        # Gross >= Net Weight
        rule_wgt1 = rule_map.get("VAL-WGT-001")
        if rule_wgt1 and rule_wgt1.enabled:
            gross_w = pl_header.get("total_gross_weight_kg")
            net_w = pl_header.get("total_net_weight_kg")
            res_wgt1 = validation_engine.validate_weights(gross_w, net_w)
            if res_wgt1:
                res_wgt1.severity = rule_wgt1.severity
                res_wgt1.source_doc_a_name = "Packing List"
                rule_results.append(res_wgt1)

        # Currency & Incoterms
        rule_cur = rule_map.get("VAL-CUR-001")
        if rule_cur and rule_cur.enabled:
            curr_ci = ci_header.get("currency")
            curr_dec = dec_header.get("currency")
            inco_ci = ci_header.get("incoterms")
            inco_dec = dec_header.get("incoterms")
            res_cur = validation_engine.validate_currency_and_incoterms(curr_ci, curr_dec, inco_ci, inco_dec)
            if res_cur:
                res_cur.severity = rule_cur.severity
                rule_results.append(res_cur)

        # 14-Field x 7-Document Cross-Document Matrix & SC / Non-SC Role Validation
        matrix_rows, extra_matrix_results, has_sc = evaluate_cross_document_matrix(documents, shipment)

        # Partner Match (Người xuất khẩu và Người nhập khẩu)
        rule_ptn = rule_map.get("VAL-PTN-001")
        if rule_ptn and rule_ptn.enabled:
            if not has_sc:
                shipper_ci = ci_header.get("shipper") or ci_header.get("seller_name") or ci_header.get("shipper_name")
                shipper_dec = dec_header.get("shipper") or dec_header.get("exporter_name") or dec_header.get("shipper_name")
                res_ptn = validation_engine.validate_partner_match(shipper_ci, shipper_dec)
                if res_ptn:
                    res_ptn.severity = rule_ptn.severity
                    rule_results.append(res_ptn)

                consignee_ci = ci_header.get("consignee") or ci_header.get("buyer_name") or ci_header.get("consignee_importer")
                consignee_dec = dec_header.get("consignee") or dec_header.get("importer_name") or dec_header.get("consignee_importer")
                res_cng = validation_engine.validate_consignee_match(consignee_ci, consignee_dec)
                if res_cng:
                    res_cng.severity = rule_ptn.severity
                    rule_results.append(res_cng)

        existing_rule_keys = {(r.rule_code, r.field_name) for r in rule_results}
        for mr in extra_matrix_results:
            if (mr.rule_code, mr.field_name) not in existing_rule_keys:
                rule_results.append(mr)
                existing_rule_keys.add((mr.rule_code, mr.field_name))

        # Persist findings into Discrepancies table
        existing_discrepancies = db.query(Discrepancy).filter(Discrepancy.shipment_id == shipment_id).all()
        existing_open_list = [d for d in existing_discrepancies if d.status == "OPEN"]
        existing_open_map = {(d.rule_code, d.field_name): d for d in existing_open_list}
        active_keys = {(r.rule_code, r.field_name) for r in rule_results}
        if persist:
            for record in existing_open_list:
                if (record.rule_code, record.field_name) not in active_keys:
                    record.status = "RESOLVED"
            db.flush()

        error_count = 0
        warning_count = 0
        active_discrepancies_by_field: Dict[str, List[str]] = {}

        for r in rule_results:
            new_d = Discrepancy(
                shipment_id=shipment_id,
                rule_code=r.rule_code,
                severity=r.severity,
                category=r.category,
                field_name=r.field_name,
                description_vi=r.description_vi,
                source_doc_a_name=r.source_doc_a_name,
                value_a=r.value_a,
                source_doc_b_name=r.source_doc_b_name,
                value_b=r.value_b,
                status="OPEN"
            )
            if persist:
                existing = existing_open_map.get((r.rule_code, r.field_name))
                if existing:
                    for attribute in ("severity", "category", "description_vi", "source_doc_a_name", "source_doc_b_name", "value_a", "value_b"):
                        setattr(existing, attribute, getattr(new_d, attribute))
                else:
                    db.add(new_d)
            if r.severity == "ERROR":
                error_count += 1
            else:
                warning_count += 1

            if r.field_name not in active_discrepancies_by_field:
                active_discrepancies_by_field[r.field_name] = []
            active_discrepancies_by_field[r.field_name].append(r.description_vi)

        # Build SKU Comparison Matrix
        sku_matrix = []
        for sku_key, data in sku_map.items():
            q_dec = data["quantities"].get("CUSTOMS_DECLARATION")
            q_ci = data["quantities"].get("COMMERCIAL_INVOICE")
            q_pl = data["quantities"].get("PACKING_LIST")
            q_po = data["quantities"].get("PURCHASE_ORDER") or data["quantities"].get("SALE_CONTRACT")

            sku_field_keys = [
                f"sku[{sku_key}].quantity",
                f"sku[{sku_key}].hs_code",
                f"sku[{sku_key}].hs_code_match",
            ]
            sku_issues = []
            for fk in sku_field_keys:
                if fk in active_discrepancies_by_field:
                    sku_issues.extend(active_discrepancies_by_field[fk])

            is_matched = len(sku_issues) == 0

            sku_matrix.append({
                "sku": data["sku"],
                "po_reference": data["po_reference"],
                "description_vi": data["description_vi"],
                "hs_code_declaration": data["hs_codes"].get("CUSTOMS_DECLARATION"),
                "hs_code_invoice": data["hs_codes"].get("COMMERCIAL_INVOICE") or data["hs_codes"].get("CUSTOMS_DECLARATION"),
                "qty_declaration": q_dec,
                "qty_invoice": q_ci,
                "qty_packing_list": q_pl,
                "qty_po": q_po,
                "unit_price_invoice": data["unit_prices"].get("COMMERCIAL_INVOICE"),
                "uom": data["uom"],
                "is_matched": is_matched,
                "discrepancies": sku_issues
            })

        if persist:
            # Update shipment status
            if error_count > 0:
                shipment.status = "DISCREPANT"
                if shipment.approval_status == "APPROVED":
                    shipment.approval_status = "PENDING"
            elif shipment.status not in ("TRANSMITTED", "APPROVED"):
                shipment.status = "VALIDATED"

            audit = AuditLog(
                shipment_id=shipment_id,
                action="REVALIDATION_TRIGGERED",
                target_entity="Shipment",
                target_id=shipment_id,
                reason=f"Tự động tái đối soát ({trigger_reason}). Kết quả: {error_count} lỗi, {warning_count} cảnh báo."
            )
            db.add(audit)
            db.commit()

        return {
            "shipment_id": shipment_id,
            "error_count": error_count,
            "warning_count": warning_count,
            "status": shipment.status,
            "total_skus": len(sku_map),
            "sku_matrix": sku_matrix,
            "field_matrix": [r.model_dump() for r in matrix_rows],
            "has_sale_contract": has_sc,
        }


reconciliation_engine = CrossDocumentReconciliationEngine()
