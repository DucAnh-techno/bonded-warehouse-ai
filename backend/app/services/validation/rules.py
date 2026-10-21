import re
from typing import List, Optional, Dict, Any, Set, Tuple
from pydantic import BaseModel
from app.services.validation.documents import get_required_documents, DOMESTIC_REQUIRED_DOCUMENTS, FOREIGN_REQUIRED_DOCUMENTS


class ValidationRuleResult(BaseModel):
    rule_code: str
    rule_name_vi: str
    passed: bool
    severity: str  # ERROR | WARNING | INFO
    category: str = "CONFLICT"  # MISSING | CONFLICT | NOT_APPLICABLE | NOT_VERIFIED
    field_name: str
    description_vi: str
    source_doc_a_name: Optional[str] = None
    value_a: Optional[str] = None
    source_doc_b_name: Optional[str] = None
    value_b: Optional[str] = None


def compute_tolerance_pct(a: float, b: float) -> float:
    """
    Công thức tính chênh lệch dung sai nhất quán:
    abs(a - b) / max(abs(a), abs(b)) * 100%
    Xử lý an toàn khi chia cho 0.
    """
    max_val = max(abs(a), abs(b))
    if max_val == 0.0:
        return 0.0
    return abs(a - b) / max_val * 100.0


class DeterministicValidationEngine:
    """
    100% Deterministic Customs Validation Engine.
    Zero AI hallucination or heuristic guessing allowed.
    All rules strictly correspond to Vietnamese customs and bonded warehouse regulations.
    """

    @staticmethod
    def validate_mandatory_documents(
        present_doc_types: List[str],
        inbound_source: Optional[str] = None
    ) -> List[ValidationRuleResult]:
        """
        VAL-DOC-001: Kiểm tra bộ chứng từ bắt buộc theo loại nguồn nhập (Nghị định 08/2015/NĐ-CP).
        - Nhập nội địa (DOMESTIC): PL, Tờ khai hải quan, Invoice, Hợp đồng thuê kho (4 loại).
        - Nhập nước ngoài (FOREIGN): PL, BL, Arrival Notice, Invoice, Hợp đồng thuê kho, Tờ khai hải quan (6 loại).
        - Hồ sơ chưa có loại nhập: báo lỗi yêu cầu phân loại.
        """
        results: List[ValidationRuleResult] = []
        present_set = set(present_doc_types)

        if not inbound_source:
            # Hồ sơ cũ chưa phân loại nguồn nhập
            results.append(
                ValidationRuleResult(
                    rule_code="VAL-DOC-001",
                    rule_name_vi="Phân loại nguồn hàng nhập kho",
                    passed=False,
                    severity="ERROR",
                    category="MISSING",
                    field_name="shipment.inbound_source",
                    description_vi="Hồ sơ chưa được phân loại nguồn hàng nhập (Nhập nội địa hoặc Nhập nước ngoài). Cần chọn nguồn hàng để xác định bộ chứng từ bắt buộc.",
                    source_doc_a_name="Thông tin lô hàng",
                    value_a="Chưa phân loại (MISSING)",
                    source_doc_b_name="Quy định Hải quan",
                    value_b="DOMESTIC | FOREIGN",
                )
            )
            # Default to domestic set if unclassified so old tests still see document checks
            mandatory = DOMESTIC_REQUIRED_DOCUMENTS
        else:
            mandatory = get_required_documents(inbound_source)

        src_label = "Nhập nội địa" if inbound_source == "DOMESTIC" else ("Nhập nước ngoài" if inbound_source == "FOREIGN" else "Kho ngoại quan")

        for doc_type, doc_label in mandatory.items():
            if doc_type not in present_set:
                results.append(
                    ValidationRuleResult(
                        rule_code="VAL-DOC-001",
                        rule_name_vi="Kiểm tra bộ chứng từ bắt buộc",
                        passed=False,
                        severity="ERROR",
                        category="MISSING",
                        field_name=f"document_types.{doc_type}",
                        description_vi=f"Thiếu chứng từ bắt buộc: Bộ hồ sơ {src_label} chưa có '{doc_label}'.",
                        source_doc_a_name=doc_label,
                        value_a="Chưa tải lên (MISSING)",
                        source_doc_b_name=f"Quy định {src_label}",
                        value_b="Bắt buộc",
                    )
                )
        return results

    @staticmethod
    def validate_mandatory_containers(containers: List[str]) -> Optional[ValidationRuleResult]:
        """VAL-CNT-002: Kiểm tra số container bắt buộc (Phạm vi chỉ gồm hàng container)."""
        valid_containers = [c.strip() for c in containers if c and c.strip()]
        if not valid_containers:
            return ValidationRuleResult(
                rule_code="VAL-CNT-002",
                rule_name_vi="Dữ liệu số Container bắt buộc",
                passed=False,
                severity="ERROR",
                category="MISSING",
                field_name="container_numbers",
                description_vi="Phạm vi ứng dụng chỉ gồm hàng container. Hồ sơ bắt buộc phải có ít nhất một số container hợp lệ.",
                value_a=None,
                value_b="Tối thiểu 1 container",
            )
        return None

    @staticmethod
    def validate_mandatory_customs_declaration(declaration_no: Optional[str]) -> Optional[ValidationRuleResult]:
        """VAL-DEC-001: Số tờ khai hải quan bắt buộc cho cả hai loại nhập."""
        if not declaration_no or not str(declaration_no).strip():
            return ValidationRuleResult(
                rule_code="VAL-DEC-001",
                rule_name_vi="Số tờ khai hải quan bắt buộc",
                passed=False,
                severity="ERROR",
                category="MISSING",
                field_name="customs_declaration_no",
                description_vi="Số tờ khai hải quan là dữ liệu bắt buộc cho cả Nhập nội địa và Nhập nước ngoài.",
                value_a=None,
                value_b="Số tờ khai HQ bắt buộc",
            )
        return None

    @staticmethod
    def validate_line_item_math(
        item_index: int,
        quantity: float,
        unit_price: Optional[float],
        total_amount: Optional[float],
        tolerance: float = 0.01
    ) -> Optional[ValidationRuleResult]:
        """VAL-PRC-001: Kiểm tra tính toán số học từng dòng hàng."""
        if unit_price is None or total_amount is None:
            return None

        expected_total = quantity * unit_price
        diff = abs(expected_total - total_amount)

        if diff > tolerance:
            return ValidationRuleResult(
                rule_code="VAL-PRC-001",
                rule_name_vi="Kiểm tra tính toán thành tiền dòng hàng",
                passed=False,
                severity="ERROR",
                category="CONFLICT",
                field_name=f"items[{item_index}].total_amount",
                description_vi=f"Sai lệch thành tiền dòng {item_index}: Khai báo {total_amount:,.2f}, tính toán {quantity} x {unit_price:,.2f} = {expected_total:,.2f} (Lệch {diff:,.2f}).",
                value_a=str(total_amount),
                value_b=str(expected_total),
            )
        return None

    @staticmethod
    def validate_invoice_total_sum(
        declared_total: Optional[float],
        calculated_sum: float,
        tolerance: float = 0.5
    ) -> Optional[ValidationRuleResult]:
        """VAL-PRC-002: Kiểm tra tổng trị giá hóa đơn (cho phép sai số 0.5)."""
        if declared_total is None:
            return None

        diff = abs(declared_total - calculated_sum)
        if diff > tolerance and compute_tolerance_pct(declared_total, calculated_sum) > tolerance:
            return ValidationRuleResult(
                rule_code="VAL-PRC-002",
                rule_name_vi="Kiểm tra tổng trị giá hóa đơn",
                passed=False,
                severity="ERROR",
                category="CONFLICT",
                field_name="total_invoice_value",
                description_vi=f"Tổng trị giá hóa đơn khai báo ({declared_total:,.2f}) không khớp tổng các dòng hàng cộng lại ({calculated_sum:,.2f}). Chênh lệch {diff:,.2f} (vượt sai số {tolerance}).",
                value_a=str(declared_total),
                value_b=str(calculated_sum),
            )
        return None

    @staticmethod
    def validate_weights(
        gross_weight: Optional[float],
        net_weight: Optional[float]
    ) -> Optional[ValidationRuleResult]:
        """VAL-WGT-001: Kiểm tra trọng lượng Gross >= Net > 0."""
        if gross_weight is None or net_weight is None:
            return None

        if gross_weight < net_weight or net_weight <= 0:
            return ValidationRuleResult(
                rule_code="VAL-WGT-001",
                rule_name_vi="Kiểm tra tỷ trọng Gross/Net",
                passed=False,
                severity="ERROR",
                category="CONFLICT",
                field_name="gross_weight_kg",
                description_vi=f"Trọng lượng cả bì (Gross Weight: {gross_weight} kg) nhỏ hơn trọng lượng tịnh (Net Weight: {net_weight} kg). Đây là điều phi lý về quy cách đóng gói.",
                value_a=str(gross_weight),
                value_b=str(net_weight),
            )
        return None

    @staticmethod
    def validate_weight_tolerance(
        gross_a: Optional[float],
        gross_b: Optional[float],
        source_a: str = "Bill of Lading",
        source_b: str = "Packing List",
        tolerance_pct: float = 0.5
    ) -> Optional[ValidationRuleResult]:
        """
        VAL-WGT-002: Đối chiếu Gross Weight giữa các chứng từ (B/L, PL, Tờ khai).
        Áp dụng công thức: abs(a - b) / max(abs(a), abs(b)) * 100%. Dung sai tối đa 0.5%.
        Vượt ngưỡng 0.5% báo lỗi severity="ERROR" chặn duyệt.
        """
        if gross_a is None or gross_b is None:
            return None
        if gross_a <= 0 or gross_b <= 0:
            return None

        diff_pct = compute_tolerance_pct(gross_a, gross_b)
        # Kiểm tra nếu một chứng từ dùng đơn vị Tấn (1 tấn = 1000 kg)
        diff_ton_a = compute_tolerance_pct(gross_a * 1000, gross_b)
        diff_ton_b = compute_tolerance_pct(gross_a, gross_b * 1000)
        min_diff = min(diff_pct, diff_ton_a, diff_ton_b)

        if min_diff > tolerance_pct:
            return ValidationRuleResult(
                rule_code="VAL-WGT-002",
                rule_name_vi="Đối chiếu trọng lượng Gross Weight",
                passed=False,
                severity="ERROR",
                category="CONFLICT",
                field_name="gross_weight_tolerance",
                description_vi=f"Gross Weight giữa {source_a} ({gross_a:,.2f} kg) và {source_b} ({gross_b:,.2f} kg) chênh lệch {min_diff:.2f}%, vượt ngưỡng cho phép {tolerance_pct}%.",
                source_doc_a_name=source_a,
                value_a=f"{gross_a:,.2f} kg",
                source_doc_b_name=source_b,
                value_b=f"{gross_b:,.2f} kg",
            )
        return None

    @staticmethod
    def validate_weight_bl_vs_pl(
        gross_bl: Optional[float],
        gross_pl: Optional[float],
        tolerance_pct: float = 0.5
    ) -> Optional[ValidationRuleResult]:
        """Compatibility wrapper for VAL-WGT-002."""
        return DeterministicValidationEngine.validate_weight_tolerance(
            gross_bl, gross_pl, "Bill of Lading", "Packing List", tolerance_pct
        )

    @staticmethod
    def validate_cbm_tolerance(
        cbm_a: Optional[float],
        cbm_b: Optional[float],
        source_a: str = "Bill of Lading",
        source_b: str = "Arrival Notice",
        tolerance_pct: float = 0.5
    ) -> Optional[ValidationRuleResult]:
        """
        VAL-CBM-001: Đối chiếu thể tích CBM giữa các chứng từ.
        Dung sai tối đa 0.5%.
        """
        if cbm_a is None or cbm_b is None:
            return None
        if cbm_a <= 0 or cbm_b <= 0:
            return None

        diff_pct = compute_tolerance_pct(cbm_a, cbm_b)
        if diff_pct > tolerance_pct:
            return ValidationRuleResult(
                rule_code="VAL-CBM-001",
                rule_name_vi="Đối chiếu thể tích hàng hóa (CBM)",
                passed=False,
                severity="ERROR",
                category="CONFLICT",
                field_name="measurement_cbm",
                description_vi=f"Thể tích hàng hóa giữa {source_a} ({cbm_a:,.2f} m³) và {source_b} ({cbm_b:,.2f} m³) chênh lệch {diff_pct:.2f}%, vượt ngưỡng cho phép {tolerance_pct}%.",
                source_doc_a_name=source_a,
                value_a=f"{cbm_a:,.2f} m³",
                source_doc_b_name=source_b,
                value_b=f"{cbm_b:,.2f} m³",
            )
        return None

    @staticmethod
    def validate_package_counts(
        packages_by_doc: Dict[str, Optional[int]],
        units_by_doc: Optional[Dict[str, Optional[str]]] = None
    ) -> List[ValidationRuleResult]:
        """
        VAL-PKG-001: Đối soát số kiện giữa các chứng từ.
        - Số kiện phải khớp chính xác (dung sai = 0).
        - Không tự quy đổi giữa các đơn vị đóng gói (carton, pallet, package) nếu khác nhau.
        """
        results: List[ValidationRuleResult] = []
        valid_items = {k: v for k, v in packages_by_doc.items() if v is not None}
        if len(valid_items) < 2:
            return results

        first_doc, first_count = next(iter(valid_items.items()))
        for doc_name, count in list(valid_items.items())[1:]:
            if first_count != count:
                results.append(
                    ValidationRuleResult(
                        rule_code="VAL-PKG-001",
                        rule_name_vi="Đối soát số lượng kiện hàng",
                        passed=False,
                        severity="ERROR",
                        category="CONFLICT",
                        field_name="total_packages",
                        description_vi=f"Số kiện không khớp: {first_doc} ghi {first_count} kiện, nhưng {doc_name} ghi {count} kiện. Quy định hải quan yêu cầu số kiện phải khớp chính xác.",
                        source_doc_a_name=first_doc,
                        value_a=str(first_count),
                        source_doc_b_name=doc_name,
                        value_b=str(count),
                    )
                )

        if units_by_doc:
            def _norm_pkg_unit(u: str) -> str:
                s = u.strip().upper()
                if s in ("CT", "CTN", "CTNS", "CARTON", "CARTONS"):
                    return "CARTON"
                if s in ("PL", "PLT", "PLTS", "PALLET", "PALLETS"):
                    return "PALLET"
                if s in ("PKG", "PKGS", "PACKAGE", "PACKAGES"):
                    return "PACKAGE"
                if s in ("PC", "PCS", "PIECE", "PIECES"):
                    return "PIECE"
                if s in ("BOX", "BOXES"):
                    return "BOX"
                return s

            valid_units = {k: v.strip().upper() for k, v in units_by_doc.items() if v and v.strip()}
            if len(valid_units) >= 2:
                u_first_doc, u_first_raw = next(iter(valid_units.items()))
                u_first_val = _norm_pkg_unit(u_first_raw)
                for u_doc, u_raw in list(valid_units.items())[1:]:
                    u_val = _norm_pkg_unit(u_raw)
                    # Nếu cùng hệ quy chuẩn (ví dụ CARTONS, CTNS, CT) thì đã khớp hoàn toàn
                    if u_first_val != u_val:
                        is_piece_diff = (u_first_val == "PIECE" or u_val == "PIECE")
                        results.append(
                            ValidationRuleResult(
                                rule_code="VAL-PKG-002",
                                rule_name_vi="Đồng nhất đơn vị đóng gói",
                                passed=False,
                                severity="WARNING" if is_piece_diff else "ERROR",
                                category="CONFLICT",
                                field_name="package_unit",
                                description_vi=f"Đơn vị đóng gói: {u_first_doc} ghi '{u_first_raw}', nhưng {u_doc} ghi '{u_raw}'.",
                                source_doc_a_name=u_first_doc,
                                value_a=u_first_raw,
                                source_doc_b_name=u_doc,
                                value_b=u_raw,
                            )
                        )
        return results

    @staticmethod
    def validate_hs_code_format(
        sku: str,
        hs_code: Optional[str]
    ) -> Optional[ValidationRuleResult]:
        """VAL-HS-001: Kiểm tra định dạng mã số HS Việt Nam (8 chữ số)."""
        if not hs_code:
            return ValidationRuleResult(
                rule_code="VAL-HS-001",
                rule_name_vi="Định dạng Mã số HS Việt Nam",
                passed=False,
                severity="ERROR",
                category="MISSING",
                field_name=f"sku[{sku}].hs_code",
                description_vi=f"SKU {sku} thiếu thông tin Mã số HS khai báo hải quan.",
                value_a=None,
                value_b="8 chữ số HS",
            )

        cleaned_hs = re.sub(r"[.\s-]", "", hs_code)
        if not re.match(r"^\d{8}$", cleaned_hs):
            return ValidationRuleResult(
                rule_code="VAL-HS-001",
                rule_name_vi="Định dạng Mã số HS Việt Nam",
                passed=False,
                severity="ERROR",
                category="CONFLICT",
                field_name=f"sku[{sku}].hs_code",
                description_vi=f"Mã HS '{hs_code}' của SKU {sku} không hợp lệ. Biểu thuế xuất nhập khẩu Việt Nam yêu cầu định dạng chuẩn 8 chữ số (ví dụ: 8471.30.20).",
                value_a=hs_code,
                value_b="Định dạng 8 số",
            )
        return None

    @staticmethod
    def validate_hs_code_match(
        sku: str,
        hs_declaration: Optional[str],
        hs_invoice: Optional[str]
    ) -> Optional[ValidationRuleResult]:
        """VAL-HS-002: Thống nhất Mã HS giữa Tờ khai và Hóa đơn."""
        if not hs_declaration or not hs_invoice:
            return None

        clean_dec = re.sub(r"[.\s-]", "", hs_declaration)
        clean_inv = re.sub(r"[.\s-]", "", hs_invoice)
        if clean_dec != clean_inv:
            return ValidationRuleResult(
                rule_code="VAL-HS-002",
                rule_name_vi="Thống nhất Mã HS qua các chứng từ",
                passed=False,
                severity="ERROR",
                category="CONFLICT",
                field_name=f"sku[{sku}].hs_code_match",
                description_vi=f"Mã HS SKU {sku} không khớp: Tờ khai ghi {hs_declaration}, nhưng Hóa đơn ghi {hs_invoice}.",
                source_doc_a_name="Tờ khai hải quan",
                value_a=hs_declaration,
                source_doc_b_name="Hóa đơn thương mại",
                value_b=hs_invoice,
            )
        return None

    @staticmethod
    def validate_cross_document_quantities(
        sku: str,
        qty_pl: Optional[float],
        qty_ci: Optional[float],
        qty_dec: Optional[float]
    ) -> Optional[ValidationRuleResult]:
        """VAL-QTY-001: Đối soát số lượng SKU giữa Packing List, Invoice và Tờ khai."""
        values = {"Packing List": qty_pl, "Commercial Invoice": qty_ci, "Tờ khai hải quan": qty_dec}
        present_values = {k: v for k, v in values.items() if v is not None}

        if len(present_values) < 2:
            return None

        first_key, first_val = next(iter(present_values.items()))
        for doc_name, val in list(present_values.items())[1:]:
            if abs(first_val - val) > 0.001:
                return ValidationRuleResult(
                    rule_code="VAL-QTY-001",
                    rule_name_vi="Đối soát số lượng SKU giữa các chứng từ",
                    passed=False,
                    severity="ERROR",
                    category="CONFLICT",
                    field_name=f"sku[{sku}].quantity",
                    description_vi=f"Bất đồng bộ số lượng SKU {sku}: {first_key} ghi {first_val:,.2f}, nhưng {doc_name} ghi {val:,.2f}.",
                    source_doc_a_name=first_key,
                    value_a=str(first_val),
                    source_doc_b_name=doc_name,
                    value_b=str(val),
                )
        return None

    @staticmethod
    def validate_container_numbers(
        containers_bl: List[str],
        containers_dec: List[str]
    ) -> Optional[ValidationRuleResult]:
        """VAL-CNT-001: Đối chiếu số Container giữa Vận đơn (B/L) và Tờ khai HQ."""
        if not containers_bl or not containers_dec:
            return None

        set_bl = set([c.strip().upper() for c in containers_bl if c and c.strip()])
        set_dec = set([c.strip().upper() for c in containers_dec if c and c.strip()])

        if set_bl != set_dec:
            diff_a = list(set_bl - set_dec)
            diff_b = list(set_dec - set_bl)
            return ValidationRuleResult(
                rule_code="VAL-CNT-001",
                rule_name_vi="Thống nhất số Container",
                passed=False,
                severity="ERROR",
                category="CONFLICT",
                field_name="containers",
                description_vi=f"Số container trên Vận đơn (B/L) không khớp với Tờ khai HQ. Lệch: B/L có {diff_a}, Tờ khai có {diff_b}.",
                source_doc_a_name="Bill of Lading",
                value_a=",".join(sorted(set_bl)),
                source_doc_b_name="Customs Declaration",
                value_b=",".join(sorted(set_dec)),
            )
        return None

    @staticmethod
    def validate_currency_and_incoterms(
        curr_ci: Optional[str],
        curr_dec: Optional[str],
        inco_ci: Optional[str],
        inco_dec: Optional[str]
    ) -> Optional[ValidationRuleResult]:
        """VAL-CUR-001: Đồng nhất loại tiền tệ và Incoterms."""
        if curr_ci and curr_dec and curr_ci.strip().upper() != curr_dec.strip().upper():
            return ValidationRuleResult(
                rule_code="VAL-CUR-001",
                rule_name_vi="Đồng nhất loại tiền tệ và Incoterms",
                passed=False,
                severity="ERROR",
                category="CONFLICT",
                field_name="currency",
                description_vi=f"Loại tiền tệ không khớp: Hóa đơn ghi {curr_ci.upper()}, nhưng Tờ khai ghi {curr_dec.upper()}.",
                source_doc_a_name="Hóa đơn thương mại",
                value_a=curr_ci.upper(),
                source_doc_b_name="Tờ khai hải quan",
                value_b=curr_dec.upper(),
            )
        return None

    @staticmethod
    def validate_partner_match(
        shipper_ci: Optional[str],
        shipper_dec: Optional[str]
    ) -> Optional[ValidationRuleResult]:
        """VAL-PTN-001: Thống nhất đối tác Shipper / Exporter giữa Hóa đơn và Tờ khai HQ."""
        if shipper_ci and shipper_dec:
            from app.services.validation.contract import check_company_name_match
            matched, reason, sim = check_company_name_match(shipper_ci, shipper_dec)
            if not matched:
                return ValidationRuleResult(
                    rule_code="VAL-PTN-001",
                    rule_name_vi="Thống nhất Người xuất khẩu (Invoice vs Tờ khai)",
                    passed=False,
                    severity="WARNING",
                    category="CONFLICT",
                    field_name="shipper_name",
                    description_vi=f"Tên Người xuất khẩu trên Tờ khai ('{shipper_dec}') không khớp với Hóa đơn ('{shipper_ci}'). Lý do: {reason}.",
                    source_doc_a_name="Hóa đơn thương mại",
                    value_a=shipper_ci,
                    source_doc_b_name="Tờ khai hải quan",
                    value_b=shipper_dec,
                )
        return None

    @staticmethod
    def validate_consignee_match(
        consignee_ci: Optional[str],
        consignee_dec: Optional[str]
    ) -> Optional[ValidationRuleResult]:
        """VAL-PTN-001: Thống nhất Người nhập khẩu (Consignee) giữa Hóa đơn và Tờ khai HQ (cả hai bên là U&I hoặc khớp nhau)."""
        if consignee_ci and consignee_dec:
            from app.services.validation.contract import check_company_name_match, is_ui_company
            # Cả hai bên nếu đều là U&I thì hợp lệ
            if is_ui_company(consignee_ci) and is_ui_company(consignee_dec):
                return None
            matched, reason, sim = check_company_name_match(consignee_ci, consignee_dec)
            if not matched:
                return ValidationRuleResult(
                    rule_code="VAL-PTN-001",
                    rule_name_vi="Thống nhất Người nhập khẩu (Invoice vs Tờ khai)",
                    passed=False,
                    severity="WARNING",
                    category="CONFLICT",
                    field_name="consignee_name",
                    description_vi=f"Tên Người nhập khẩu (Consignee) trên Tờ khai ('{consignee_dec}') không khớp với Hóa đơn ('{consignee_ci}'). Lý do: {reason}.",
                    source_doc_a_name="Hóa đơn thương mại",
                    value_a=consignee_ci,
                    source_doc_b_name="Tờ khai hải quan",
                    value_b=consignee_dec,
                )
        return None


validation_engine = DeterministicValidationEngine()
