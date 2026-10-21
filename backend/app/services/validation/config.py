from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models.validation import ValidationRuleSetting

DEFAULT_RULE_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "rule_code": "VAL-DOC-001",
        "name_vi": "Kiểm tra bộ chứng từ cốt lõi bắt buộc",
        "description_vi": "Bản demo bắt buộc Invoice, PL và hợp đồng thuê kho.",
        "severity": "ERROR",
        "enabled": True,
        "tolerance": None,
        "category": "MISSING",
    },
    {
        "rule_code": "VAL-QTY-001",
        "name_vi": "Đối soát cân bằng số lượng SKU",
        "description_vi": "Cộng số lượng theo từng PO/SKU trên PL và Invoice rồi đối chiếu.",
        "severity": "ERROR",
        "enabled": True,
        "tolerance": 0.001,
        "category": "CONFLICT",
    },
    {
        "rule_code": "VAL-PRC-001",
        "name_vi": "Kiểm tra tính toán số học từng dòng hàng",
        "description_vi": "Số lượng x Đơn giá == Thành tiền dòng hàng (Line Total). Dung sai cho phép tính theo USD.",
        "severity": "ERROR",
        "enabled": True,
        "tolerance": 0.01,
        "category": "CONFLICT",
    },
    {
        "rule_code": "VAL-PRC-002",
        "name_vi": "Kiểm tra tổng trị giá hóa đơn",
        "description_vi": "Tổng các dòng hàng cộng lại == Tổng trị giá hóa đơn khai báo (cho phép sai số 0.5).",
        "severity": "ERROR",
        "enabled": True,
        "tolerance": 0.5,
        "category": "CONFLICT",
    },
    {
        "rule_code": "VAL-WGT-001",
        "name_vi": "Kiểm tra tỷ trọng Gross / Net",
        "description_vi": "Trọng lượng cả bì (Gross Weight) phải lớn hơn hoặc bằng trọng lượng tịnh (Net Weight) > 0.",
        "severity": "ERROR",
        "enabled": True,
        "tolerance": None,
        "category": "CONFLICT",
    },
    {
        "rule_code": "VAL-WGT-002",
        "name_vi": "Đối chiếu trọng lượng Vận đơn (B/L) và Phiếu đóng gói",
        "description_vi": "Chênh lệch Gross Weight giữa Vận đơn và Packing List không được vượt quá dung sai % cho phép.",
        "severity": "WARNING",
        "enabled": True,
        "tolerance": 0.5,
        "category": "CONFLICT",
    },
    {
        "rule_code": "VAL-CNT-001",
        "name_vi": "Thống nhất số Container và Chì niêm phong",
        "description_vi": "Số Container và Chì niêm phong trên Vận đơn (B/L) phải khớp với Tờ khai HQ và Packing List.",
        "severity": "ERROR",
        "enabled": True,
        "tolerance": None,
        "category": "CONFLICT",
    },
    {
        "rule_code": "VAL-HS-001",
        "name_vi": "Định dạng Mã số HS Việt Nam",
        "description_vi": "Mã số HS phải có chuẩn 8 chữ số theo Biểu thuế XNK Việt Nam (ví dụ: 8471.30.20).",
        "severity": "ERROR",
        "enabled": True,
        "tolerance": None,
        "category": "CONFLICT",
    },
    {
        "rule_code": "VAL-HS-002",
        "name_vi": "Thống nhất Mã HS qua các chứng từ",
        "description_vi": "Mã HS của từng SKU trên Tờ khai HQ phải khớp với Hóa đơn thương mại.",
        "severity": "ERROR",
        "enabled": True,
        "tolerance": None,
        "category": "CONFLICT",
    },
    {
        "rule_code": "VAL-PO-001",
        "name_vi": "Khớp đơn đặt hàng PO và hạn mức",
        "description_vi": "SKU và số lượng nhập kho phải tương ứng với đơn đặt hàng PO và không vượt quá hạn mức.",
        "severity": "ERROR",
        "enabled": True,
        "tolerance": None,
        "category": "CONFLICT",
    },
    {
        "rule_code": "VAL-PTN-001",
        "name_vi": "Thống nhất đối tác Shipper / Consignee",
        "description_vi": "Tên người gửi hàng và người nhận hàng phải thống nhất giữa Hóa đơn, Vận đơn và Tờ khai HQ.",
        "severity": "WARNING",
        "enabled": True,
        "tolerance": None,
        "category": "CONFLICT",
    },
    {
        "rule_code": "VAL-CUR-001",
        "name_vi": "Đồng nhất loại tiền tệ và Incoterms",
        "description_vi": "Đồng tiền thanh toán (USD, EUR, VND...) và điều kiện giao hàng (CIF, FOB, EXW...) phải khớp giữa Hóa đơn và Tờ khai.",
        "severity": "ERROR",
        "enabled": True,
        "tolerance": None,
        "category": "CONFLICT",
    },
]


def seed_default_rules(db: Session) -> None:
    """Khởi tạo các quy tắc đối soát mặc định nếu chưa có trong DB."""
    existing_codes = {r.rule_code for r in db.query(ValidationRuleSetting).all()}
    for r_def in DEFAULT_RULE_DEFINITIONS:
        if r_def["rule_code"] not in existing_codes:
            setting = ValidationRuleSetting(
                rule_code=r_def["rule_code"],
                name_vi=r_def["name_vi"],
                description_vi=r_def["description_vi"],
                severity=r_def["severity"],
                enabled=r_def["enabled"],
                tolerance=r_def["tolerance"],
                category=r_def["category"],
            )
            db.add(setting)
    db.commit()


def get_all_rule_settings(db: Session) -> List[ValidationRuleSetting]:
    """Lấy danh sách cài đặt quy tắc đối soát hiện tại."""
    seed_default_rules(db)
    return db.query(ValidationRuleSetting).order_by(ValidationRuleSetting.rule_code).all()


def get_rule_map(db: Session) -> Dict[str, ValidationRuleSetting]:
    """Lấy map tra cứu quy tắc theo mã rule_code."""
    rules = get_all_rule_settings(db)
    return {r.rule_code: r for r in rules}
