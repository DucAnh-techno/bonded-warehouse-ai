import re
import unicodedata
from datetime import date
from difflib import SequenceMatcher
from typing import Optional, List, Tuple
from app.services.validation.rules import ValidationRuleResult


def remove_vietnamese_accents(text: str) -> str:
    nfkd = unicodedata.normalize('NFKD', text)
    result = ''.join([c for c in nfkd if not unicodedata.combining(c)])
    return result.replace('đ', 'd').replace('Đ', 'D')


def normalize_company_name(name: Optional[str]) -> str:
    if not name:
        return ""
    s = remove_vietnamese_accents(name).upper().strip()
    s = re.sub(r"\bCTY\b", "CONG TY", s)
    s = re.sub(r"\bCP\b", "CO PHAN", s)
    s = re.sub(r"\bTNHH\b", "TRACH NHIEM HUU HAN", s)
    s = re.sub(r"\bMTV\b", "MOT THANH VIEN", s)
    s = re.sub(r"\bJSC\b", "CO PHAN", s)
    s = re.sub(r"\bCO\.,?\s*LTD\b", "TRACH NHIEM HUU HAN", s)
    s = re.sub(r"\bLTD\b", "TRACH NHIEM HUU HAN", s)
    s = re.sub(r"\bLLC\b", "TRACH NHIEM HUU HAN", s)
    s = re.sub(r"\bCORP\b", "TAP DOAN", s)
    s = re.sub(r"\bCORPORATION\b", "TAP DOAN", s)
    s = re.sub(r"\bINC\b", "", s)
    s = re.sub(r"\bVN\b", "VIET NAM", s)
    s = re.sub(r"\bVIETNAM\b", "VIET NAM", s)
    s = re.sub(r"[^\w\s]", " ", s)
    return " ".join([w for w in s.split() if w])


def strip_corporate_tokens(norm: str) -> str:
    corp = {
        "CONG", "TY", "CO", "PHAN", "TRACH", "NHIEM", "HUU", "HAN",
        "MOT", "THANH", "VIEN", "TAP", "DOAN", "LIMITED", "COMPANY", "CORPORATION",
        "LLC", "LTD", "CORP"
    }
    return " ".join([w for w in norm.split() if w not in corp])


def check_company_name_match(name1: Optional[str], name2: Optional[str]) -> Tuple[bool, str, float]:
    """
    So sánh tên chủ hàng và bên thuê kho:
    - Chuẩn hóa loại hình doanh nghiệp, khoảng trắng, bỏ dấu
    - Cho phép tên gần giống tự được chấp nhận khi đủ chắc chắn (ngưỡng >= 0.88)
    - Tên khác nhau rõ ràng (ví dụ: Biển Đông vs Phương Đông) bị từ chối
    """
    if not name1 or not name2:
        return False, "Thiếu dữ liệu tên để đối chiếu", 0.0

    n1 = normalize_company_name(name1)
    n2 = normalize_company_name(name2)
    if not n1 or not n2:
        return False, "Tên không hợp lệ sau chuẩn hóa", 0.0

    if n1 == n2:
        return True, "Khớp chính xác sau chuẩn hóa loại hình doanh nghiệp", 1.0

    c1 = strip_corporate_tokens(n1)
    c2 = strip_corporate_tokens(n2)
    if c1 and c2 and c1 == c2:
        return True, f"Khớp thương hiệu cốt lõi ('{c1}') sau khi chuẩn hóa", 0.95

    # Khớp tên cốt lõi nếu một chuỗi chứa tên công ty và chuỗi kia kèm địa chỉ / mã số
    if c1 and c2 and len(min(c1, c2, key=len)) >= 3:
        shorter, longer = (c1, c2) if len(c1) < len(c2) else (c2, c1)
        if longer.startswith(shorter) or f" {shorter} " in f" {longer} ":
            return True, f"Khớp tên cốt lõi ('{shorter}') trong thông tin doanh nghiệp", 0.95

    sim = SequenceMatcher(None, c1, c2).ratio() if c1 and c2 else 0.0
    t1 = set(c1.split())
    t2 = set(c2.split())
    jac = len(t1 & t2) / len(t1 | t2) if (t1 and t2) else 0.0

    if sim >= 0.88 and jac >= 0.75:
        return True, f"Tên gần giống được tự động chấp nhận (độ tương đồng {sim:.2f})", sim

    return False, f"Tên doanh nghiệp không khớp (độ tương đồng {sim:.2f} < ngưỡng 0.88)", sim


def is_ui_company(name: Optional[str]) -> bool:
    """Kiểm tra nếu chủ hàng/đối tác là công ty U&I (U&I Logistics, U & I, v.v.)."""
    if not name:
        return False
    clean = remove_vietnamese_accents(name).upper()
    if "U&I" in clean.replace(" ", ""):
        return True
    tokens = re.sub(r"[^A-Z0-9]", " ", clean).split()
    for i in range(len(tokens) - 1):
        if tokens[i] == "U" and tokens[i + 1] == "I":
            return True
    return False


def validate_contract(
    header: dict,
    entry_date: Optional[date] = None,
    exporters: Optional[List[Optional[str]]] = None,
    consignees: Optional[List[Optional[str]]] = None,
    source: str = "Hợp đồng thuê kho",
    owners: Optional[List[Optional[str]]] = None,
) -> List[ValidationRuleResult]:
    """
    Kiểm tra hợp đồng thuê kho:
    - Đầy đủ các trường: số HĐ, bên thuê, bên cho thuê, tên kho, ngày bắt đầu hiệu lực.
    - Hợp đồng thuê kho không cần kiểm tra ngày hết hiệu lực (valid_until).
    - Người xuất khẩu ở Invoice / Tờ khai = Bên thuê kho (Hợp đồng thuê kho), hoặc Bên thuê kho = Consignee/Owner.
    - Người nhập khẩu (Consignee) là công ty U&I (đại lý kho ngoại quan) là hoàn toàn hợp lệ.
    """
    results: List[ValidationRuleResult] = []

    def fail(field: str, message: str, a=None, b=None, category: str = "CONFLICT"):
        results.append(
            ValidationRuleResult(
                rule_code="VAL-CONTRACT-001",
                rule_name_vi="Hợp đồng thuê kho",
                passed=False,
                severity="ERROR",
                category=category,
                field_name=f"contract[{source}].{field}",
                description_vi=message,
                source_doc_a_name=source,
                value_a=None if a is None else str(a),
                source_doc_b_name="Quy định hợp đồng kho",
                value_b=None if b is None else str(b),
            )
        )

    # 1. Kiểm tra các trường bắt buộc trên hợp đồng (không bắt buộc ngày hiệu lực valid_from/valid_until)
    for key, label in {
        "document_number": "số hợp đồng",
        "tenant_name": "bên thuê",
        "lessor_name": "bên cho thuê",
        "warehouse_name": "tên kho",
    }.items():
        if not header.get(key):
            fail(key, f"Hợp đồng thuê kho thiếu {label}; cần kiểm tra chứng từ gốc.", category="MISSING")

    # 2. Kiểm tra ngày bắt đầu hiệu lực với NGÀY HÀNG ĐẾN THỰC TẾ (entry_date) nếu có
    valid_from_str = header.get("valid_from")
    if valid_from_str:
        try:
            start = date.fromisoformat(valid_from_str)
            if entry_date and entry_date < start:
                fail(
                    "validity",
                    f"Thời gian hàng đến thực tế ({entry_date}) trước ngày bắt đầu hiệu lực hợp đồng ({start}).",
                    a=str(entry_date),
                    b=f">= {start}"
                )
        except ValueError:
            fail("validity", "Ngày bắt đầu hiệu lực hợp đồng không đúng định dạng chuẩn YYYY-MM-DD.")

    # 3. So tên bên thuê kho (Tenant) với Người xuất khẩu (Exporter) hoặc Chủ hàng (Consignee/Owner)
    tenant_name = header.get("tenant_name")
    candidates: List[str] = []
    if exporters:
        candidates.extend([e for e in exporters if e])
    if owners:
        candidates.extend([o for o in owners if o])
    if consignees:
        candidates.extend([c for c in consignees if c])

    if tenant_name and candidates:
        if is_ui_company(tenant_name):
            pass
        else:
            any_matched = False
            last_reason = ""
            for cand in candidates:
                if is_ui_company(cand):
                    continue
                matched, reason, sim = check_company_name_match(tenant_name, cand)
                if matched:
                    any_matched = True
                    break
                else:
                    last_reason = reason

            # Nếu tất cả candidates đều là U&I (ví dụ consignee là U&I), tenant_name là đối tác thuê kho hợp lệ
            non_ui_candidates = [c for c in candidates if not is_ui_company(c)]
            if not non_ui_candidates:
                any_matched = True

            if not any_matched:
                fail(
                    "tenant_match",
                    f"Bên thuê kho ('{tenant_name}') không khớp với Người xuất khẩu hoặc Chủ hàng trên chứng từ. Lý do: {last_reason}.",
                    a=tenant_name,
                    b=", ".join(set(candidates))
                )

    # 4. Kiểm tra Người nhập khẩu (Consignee)
    # - Consignee là công ty U&I -> hợp lệ
    # - Hoặc Consignee khớp với bên thuê kho -> hợp lệ
    if consignees and tenant_name:
        for index, c in enumerate(consignees):
            if not c:
                continue
            if is_ui_company(c):
                continue
            matched, reason, sim = check_company_name_match(tenant_name, c)
            if not matched:
                fail(
                    f"consignee[{index}]",
                    f"Người nhập khẩu (Consignee) '{c}' không khớp với bên thuê kho và không phải công ty U&I.",
                    a=c,
                    b="U&I LOGISTICS"
                )

    return results
