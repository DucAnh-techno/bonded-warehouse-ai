import pytest
from app.services import validation_engine


def test_line_item_math_pass():
    result = validation_engine.validate_line_item_math(
        item_index=1,
        quantity=100.0,
        unit_price=25.50,
        total_amount=2550.00
    )
    assert result is None


def test_line_item_math_fail():
    result = validation_engine.validate_line_item_math(
        item_index=1,
        quantity=100.0,
        unit_price=25.50,
        total_amount=2500.00  # Expected 2550
    )
    assert result is not None
    assert result.rule_code == "VAL-PRC-001"
    assert result.passed is False
    assert result.severity == "ERROR"


def test_invoice_total_sum_pass():
    result = validation_engine.validate_invoice_total_sum(
        declared_total=5000.00,
        calculated_sum=5000.00
    )
    assert result is None


def test_invoice_total_sum_fail():
    result = validation_engine.validate_invoice_total_sum(
        declared_total=5000.00,
        calculated_sum=4800.00
    )
    assert result is not None
    assert result.rule_code == "VAL-PRC-002"
    assert result.passed is False


def test_weights_valid():
    result = validation_engine.validate_weights(gross_weight=1500.0, net_weight=1200.0)
    assert result is None


def test_weights_invalid_gross_less_than_net():
    result = validation_engine.validate_weights(gross_weight=800.0, net_weight=1200.0)
    assert result is not None
    assert result.rule_code == "VAL-WGT-001"
    assert result.severity == "ERROR"


def test_hs_code_format_valid():
    assert validation_engine.validate_hs_code_format("SKU-001", "84713020") is None
    assert validation_engine.validate_hs_code_format("SKU-002", "8471.30.20") is None


def test_hs_code_format_invalid():
    res1 = validation_engine.validate_hs_code_format("SKU-001", "8471")  # Too short
    assert res1 is not None
    assert res1.rule_code == "VAL-HS-001"

    res2 = validation_engine.validate_hs_code_format("SKU-002", None)  # Missing
    assert res2 is not None


def test_cross_document_quantities_match():
    result = validation_engine.validate_cross_document_quantities(
        sku="SKU-CPU-01",
        qty_pl=500.0,
        qty_ci=500.0,
        qty_dec=500.0
    )
    assert result is None


def test_cross_document_quantities_mismatch():
    result = validation_engine.validate_cross_document_quantities(
        sku="SKU-CPU-01",
        qty_pl=500.0,
        qty_ci=480.0,
        qty_dec=500.0
    )
    assert result is not None
    assert result.rule_code == "VAL-QTY-001"
    assert result.severity == "ERROR"
    assert "480" in result.description_vi


def test_container_numbers_match():
    result = validation_engine.validate_container_numbers(
        containers_bl=["TGHU1234567", "MSKU7654321"],
        containers_dec=["TGHU1234567", "MSKU7654321"]
    )
    assert result is None


def test_container_numbers_mismatch():
    result = validation_engine.validate_container_numbers(
        containers_bl=["TGHU1234567"],
        containers_dec=["TGHU9999999"]
    )
    assert result is not None
    assert result.rule_code == "VAL-CNT-001"


def test_mandatory_documents_all_present():
    present = ["COMMERCIAL_INVOICE", "PACKING_LIST", "CUSTOMS_DECLARATION"]
    results = validation_engine.validate_mandatory_documents(present, inbound_source="DOMESTIC")
    assert len(results) == 0


def test_mandatory_documents_missing_contract():
    present = ["BILL_OF_LADING", "ARRIVAL_NOTICE", "COMMERCIAL_INVOICE", "PACKING_LIST", "CUSTOMS_DECLARATION"]
    results = validation_engine.validate_mandatory_documents(present, inbound_source="FOREIGN")
    assert len(results) == 1
    assert results[0].rule_code == "VAL-DOC-001"
    assert results[0].category == "MISSING"
    assert "WAREHOUSE_CONTRACT" in results[0].field_name


def test_hs_code_match_pass():
    res = validation_engine.validate_hs_code_match("SKU-001", "8471.30.20", "84713020")
    assert res is None


def test_hs_code_match_fail():
    res = validation_engine.validate_hs_code_match("SKU-001", "8471.30.20", "8517.62.59")
    assert res is not None
    assert res.rule_code == "VAL-HS-002"
    assert res.severity == "ERROR"
    assert res.category == "CONFLICT"


def test_weight_bl_vs_pl_within_tolerance():
    # 1000 kg vs 1004 kg (0.4% diff <= 0.5% tolerance)
    res = validation_engine.validate_weight_bl_vs_pl(1000.0, 1004.0, tolerance_pct=0.5)
    assert res is None


def test_weight_bl_vs_pl_exceeds_tolerance():
    # 1000 kg vs 1010 kg (1.0% diff > 0.5% tolerance)
    res = validation_engine.validate_weight_bl_vs_pl(1000.0, 1010.0, tolerance_pct=0.5)
    assert res is not None
    assert res.rule_code == "VAL-WGT-002"
    assert res.severity == "ERROR"


def test_currency_and_incoterms_match():
    assert validation_engine.validate_currency_and_incoterms("USD", "USD", "CIF", "CIF") is None


def test_currency_and_incoterms_mismatch():
    res = validation_engine.validate_currency_and_incoterms("EUR", "USD", "CIF", "CIF")
    assert res is not None
    assert res.rule_code == "VAL-CUR-001"
    assert res.severity == "ERROR"


def test_partner_match_uniform():
    res = validation_engine.validate_partner_match("FOXCONN PRECISION VN", "Foxconn Precision VN LLC")
    assert res is None


def test_partner_match_discrepancy():
    res = validation_engine.validate_partner_match("FOXCONN PRECISION", "SAMSUNG ELECTRONICS")
    assert res is not None
    assert res.rule_code == "VAL-PTN-001"
    assert res.severity == "WARNING"

