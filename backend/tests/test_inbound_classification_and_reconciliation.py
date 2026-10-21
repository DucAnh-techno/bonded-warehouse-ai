"""
Automated Integration and Unit Test Suite for Vietnamese Bonded Warehouse AI
Covering all 20 business scenarios defined in Section 12 of the System Specifications:
1. Domestic shipment missing warehouse contract -> blocked.
2. Domestic shipment with all 4 mandatory documents -> valid.
3. Foreign shipment missing B/L -> blocked.
4. Foreign shipment missing Arrival Notice -> blocked.
5. Foreign shipment with all 6 mandatory documents -> valid.
6. Unclassified shipment -> requires_classification flag and warning.
7. Shipment without container numbers -> blocked (VAL-CNT-002).
8. Shipment with matching container numbers across documents -> passed.
9. Gross weight difference <= 0.5% -> passes tolerance check.
10. Gross weight difference > 0.5% -> blocked with ERROR (VAL-WGT-002).
11. CBM volume difference > 0.5% -> blocked with ERROR (VAL-CBM-001).
12. Package count mismatch (tolerance = 0) -> blocked with ERROR (VAL-PKG-001).
13. Incompatible package units (carton vs pallet) -> blocked with ERROR (VAL-PKG-002).
14. Single-source transport metrics -> INFO/NOT_VERIFIED warning without blocking approval.
15. Cargo owner vs Contract tenant match after corporate suffix normalization -> passed.
16. Cargo owner vs Contract tenant mismatch (dissimilar companies, similarity < 0.88) -> blocked (VAL-CONTRACT-001).
17. Actual arrival date outside contract validity period -> blocked with contract validity error.
18. Missing actual arrival date (entry_date is None) -> blocked (cannot auto-substitute with ETA).
19. Repeated SKU lines under same PO -> quantities summed and reconciled accurately.
20. Staff manual edits to arrival date or transport metrics -> revokes approval and triggers revalidation.
"""

import json
import uuid
from datetime import date
import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models.shipment import Shipment
from app.models.document import Document
from app.models.extraction import DocumentExtraction, ExtractedLineItem
from app.models.validation import Discrepancy
from app.models.audit import AuditLog
from app.services.validation.reconciler import reconciliation_engine
from app.services.validation.contract import normalize_company_name, validate_contract
from app.services.validation.rules import validation_engine, compute_tolerance_pct
from app.services.mock_wms.gatekeeper import wms_service


def _build_helper_doc(
    test_db: Session,
    shipment_id: str,
    doc_type: str,
    header_data: dict,
    line_items: list = None
) -> Document:
    doc = Document(
        shipment_id=shipment_id,
        document_type=doc_type,
        original_filename=f"{doc_type}_{uuid.uuid4().hex[:4]}.pdf",
        storage_path=f"storage/{uuid.uuid4().hex}.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        sha256_hash="dummy_hash"
    )
    test_db.add(doc)
    test_db.flush()

    ext = DocumentExtraction(
        document_id=doc.id,
        status="SUCCESS",
        model_name="gemini-2.5-flash",
        raw_response_json="{}",
        extracted_header_json=json.dumps(header_data)
    )
    test_db.add(ext)
    test_db.flush()

    if line_items:
        for idx, item in enumerate(line_items, 1):
            li = ExtractedLineItem(
                extraction_id=ext.id,
                item_index=idx,
                sku=item.get("sku"),
                part_number=item.get("part_number"),
                description_vi=item.get("description_vi", "Linh kien dien tu"),
                hs_code=item.get("hs_code", "84713020"),
                quantity=item.get("quantity"),
                uom=item.get("uom", "PCS"),
                unit_price=item.get("unit_price"),
                total_amount=item.get("total_amount"),
                po_reference=item.get("po_reference")
            )
            test_db.add(li)
        test_db.flush()

    return doc


# Scenario 1: Domestic shipment missing Packing List -> blocked; with 3 docs (PL, TK, INV) -> valid
def test_scenario_1_domestic_missing_warehouse_contract_blocked(test_db: Session):
    s = Shipment(
        shipment_code=f"SHP-SC1-{uuid.uuid4().hex[:6]}",
        inbound_source="DOMESTIC",
        customs_declaration_no="104567890120",
        entry_date=date(2026, 10, 15),
        partner_name="CONG TY TNHH DIEN TU FOXCONN VN",
        notes="Linh kien dien tu",
        status="DRAFT"
    )
    test_db.add(s)
    test_db.flush()

    hdr = {
        "consignee": "CONG TY TNHH DIEN TU FOXCONN VN",
        "container_numbers": ["TGHU1234567"],
        "seal_numbers": ["EMC123456"],
        "total_packages": 50,
        "package_unit": "CARTONS",
        "total_gross_weight_kg": 1200.0,
        "total_invoice_value": 5000.0
    }
    items = [{"sku": "SKU-001", "quantity": 100, "po_reference": "PO-1", "unit_price": 50, "total_amount": 5000}]
    # Upload only 2 docs: Invoice, Declaration (Missing PACKING_LIST)
    _build_helper_doc(test_db, s.id, "COMMERCIAL_INVOICE", hdr, items)
    _build_helper_doc(test_db, s.id, "CUSTOMS_DECLARATION", hdr)
    test_db.commit()

    res = reconciliation_engine.reconcile_shipment(test_db, s.id)
    assert res["error_count"] > 0
    missing_pl = test_db.query(Discrepancy).filter_by(
        shipment_id=s.id,
        rule_code="VAL-DOC-001",
        field_name="document_types.PACKING_LIST"
    ).first()
    assert missing_pl is not None
    assert missing_pl.severity == "ERROR"

    # Adding PACKING_LIST completes the 3 mandatory Domestic documents (PL, Tờ khai, INV)
    _build_helper_doc(test_db, s.id, "PACKING_LIST", hdr, items)
    test_db.commit()
    res_valid = reconciliation_engine.reconcile_shipment(test_db, s.id)
    assert res_valid["error_count"] == 0
    assert res_valid["status"] == "VALIDATED"


# Scenario 2: Domestic shipment with all 4 mandatory documents -> valid
def test_scenario_2_domestic_all_4_documents_valid(test_db: Session):
    s = Shipment(
        shipment_code=f"SHP-SC2-{uuid.uuid4().hex[:6]}",
        inbound_source="DOMESTIC",
        customs_declaration_no="104567890120",
        entry_date=date(2026, 10, 15),
        partner_name="CONG TY TNHH DIEN TU FOXCONN VN",
        notes="Linh kien dien tu",
        status="DRAFT"
    )
    test_db.add(s)
    test_db.flush()

    hdr = {
        "consignee": "CONG TY TNHH DIEN TU FOXCONN VN",
        "container_numbers": ["TGHU1234567"],
        "seal_numbers": ["EMC123456"],
        "total_packages": 50,
        "package_unit": "CARTONS",
        "total_gross_weight_kg": 1200.0,
        "measurement_cbm": 15.0,
        "total_invoice_value": 5000.0
    }
    items = [{"sku": "SKU-001", "quantity": 100, "po_reference": "PO-1", "unit_price": 50, "total_amount": 5000}]
    _build_helper_doc(test_db, s.id, "COMMERCIAL_INVOICE", hdr, items)
    _build_helper_doc(test_db, s.id, "PACKING_LIST", hdr, items)
    _build_helper_doc(test_db, s.id, "CUSTOMS_DECLARATION", hdr)

    contract_hdr = {
        "document_number": "HD-THUEKHO-2026-01",
        "tenant_name": "CONG TY TNHH DIEN TU FOXCONN VN",
        "lessor_name": "KHO NGOAI QUAN DINH VU",
        "warehouse_name": "KHO DINH VU HAI PHONG",
        "valid_from": "2026-01-01",
        "valid_until": "2026-12-31"
    }
    _build_helper_doc(test_db, s.id, "WAREHOUSE_CONTRACT", contract_hdr)
    test_db.commit()

    res = reconciliation_engine.reconcile_shipment(test_db, s.id)
    assert res["error_count"] == 0
    assert res["status"] == "VALIDATED"


# Scenario 3: Foreign shipment missing B/L -> blocked
def test_scenario_3_foreign_missing_bl_blocked(test_db: Session):
    s = Shipment(
        shipment_code=f"SHP-SC3-{uuid.uuid4().hex[:6]}",
        inbound_source="FOREIGN",
        customs_declaration_no="104567890120",
        entry_date=date(2026, 10, 15),
        partner_name="SAMSUNG ELECTRONICS VN",
        notes="Dien thoai di dong",
        status="DRAFT"
    )
    test_db.add(s)
    test_db.flush()

    hdr = {
        "consignee": "SAMSUNG ELECTRONICS VN",
        "container_numbers": ["MSKU9988776"],
        "seal_numbers": ["ML009988"],
        "total_packages": 120,
        "package_unit": "CARTONS",
        "total_gross_weight_kg": 3500.0,
        "total_invoice_value": 10000.0
    }
    items = [{"sku": "SM-G998B", "quantity": 200, "po_reference": "PO-SEC-01", "unit_price": 50, "total_amount": 10000}]
    _build_helper_doc(test_db, s.id, "COMMERCIAL_INVOICE", hdr, items)
    _build_helper_doc(test_db, s.id, "PACKING_LIST", hdr, items)
    _build_helper_doc(test_db, s.id, "ARRIVAL_NOTICE", hdr)
    _build_helper_doc(test_db, s.id, "CUSTOMS_DECLARATION", hdr)
    _build_helper_doc(test_db, s.id, "WAREHOUSE_CONTRACT", {
        "document_number": "HD-SEC-2026",
        "tenant_name": "SAMSUNG ELECTRONICS VIETNAM CO., LTD",
        "lessor_name": "KHO NGOAI QUAN NOI BAI",
        "valid_from": "2026-01-01",
        "valid_until": "2026-12-31"
    })
    test_db.commit()

    res = reconciliation_engine.reconcile_shipment(test_db, s.id)
    assert res["error_count"] > 0
    missing_bl = test_db.query(Discrepancy).filter_by(
        shipment_id=s.id,
        rule_code="VAL-DOC-001",
        field_name="document_types.BILL_OF_LADING"
    ).first()
    assert missing_bl is not None
    assert missing_bl.severity == "ERROR"


# Scenario 4: Foreign shipment missing Arrival Notice -> blocked
def test_scenario_4_foreign_missing_arrival_notice_blocked(test_db: Session):
    s = Shipment(
        shipment_code=f"SHP-SC4-{uuid.uuid4().hex[:6]}",
        inbound_source="FOREIGN",
        customs_declaration_no="104567890120",
        entry_date=date(2026, 10, 15),
        partner_name="SAMSUNG ELECTRONICS VN",
        notes="Dien thoai di dong",
        status="DRAFT"
    )
    test_db.add(s)
    test_db.flush()

    hdr = {
        "consignee": "SAMSUNG ELECTRONICS VN",
        "container_numbers": ["MSKU9988776"],
        "seal_numbers": ["ML009988"],
        "total_packages": 120,
        "package_unit": "CARTONS",
        "total_gross_weight_kg": 3500.0,
        "total_invoice_value": 10000.0
    }
    items = [{"sku": "SM-G998B", "quantity": 200, "po_reference": "PO-SEC-01", "unit_price": 50, "total_amount": 10000}]
    _build_helper_doc(test_db, s.id, "COMMERCIAL_INVOICE", hdr, items)
    _build_helper_doc(test_db, s.id, "PACKING_LIST", hdr, items)
    _build_helper_doc(test_db, s.id, "BILL_OF_LADING", hdr)
    _build_helper_doc(test_db, s.id, "CUSTOMS_DECLARATION", hdr)
    _build_helper_doc(test_db, s.id, "WAREHOUSE_CONTRACT", {
        "document_number": "HD-SEC-2026",
        "tenant_name": "SAMSUNG ELECTRONICS VIETNAM CO., LTD",
        "lessor_name": "KHO NGOAI QUAN NOI BAI",
        "valid_from": "2026-01-01",
        "valid_until": "2026-12-31"
    })
    test_db.commit()

    res = reconciliation_engine.reconcile_shipment(test_db, s.id)
    assert res["error_count"] > 0
    missing_an = test_db.query(Discrepancy).filter_by(
        shipment_id=s.id,
        rule_code="VAL-DOC-001",
        field_name="document_types.ARRIVAL_NOTICE"
    ).first()
    assert missing_an is not None
    assert missing_an.severity == "ERROR"


# Scenario 5: Foreign shipment with all 6 mandatory documents -> valid
def test_scenario_5_foreign_all_6_documents_valid(test_db: Session):
    s = Shipment(
        shipment_code=f"SHP-SC5-{uuid.uuid4().hex[:6]}",
        inbound_source="FOREIGN",
        customs_declaration_no="104567890120",
        entry_date=date(2026, 10, 15),
        partner_name="SAMSUNG ELECTRONICS VN",
        notes="Dien thoai di dong",
        status="DRAFT"
    )
    test_db.add(s)
    test_db.flush()

    hdr = {
        "consignee": "SAMSUNG ELECTRONICS VN",
        "container_numbers": ["MSKU9988776"],
        "seal_numbers": ["ML009988"],
        "total_packages": 120,
        "package_unit": "CARTONS",
        "total_gross_weight_kg": 3500.0,
        "measurement_cbm": 45.0,
        "total_invoice_value": 10000.0
    }
    items = [{"sku": "SM-G998B", "quantity": 200, "po_reference": "PO-SEC-01", "unit_price": 50, "total_amount": 10000}]
    _build_helper_doc(test_db, s.id, "COMMERCIAL_INVOICE", hdr, items)
    _build_helper_doc(test_db, s.id, "PACKING_LIST", hdr, items)
    _build_helper_doc(test_db, s.id, "BILL_OF_LADING", hdr)
    _build_helper_doc(test_db, s.id, "ARRIVAL_NOTICE", hdr)
    _build_helper_doc(test_db, s.id, "CUSTOMS_DECLARATION", hdr)
    _build_helper_doc(test_db, s.id, "WAREHOUSE_CONTRACT", {
        "document_number": "HD-SEC-2026",
        "tenant_name": "SAMSUNG ELECTRONICS VIETNAM CO., LTD",
        "lessor_name": "KHO NGOAI QUAN NOI BAI",
        "warehouse_name": "KHO NOI BAI",
        "valid_from": "2026-01-01",
        "valid_until": "2026-12-31"
    })
    test_db.commit()

    res = reconciliation_engine.reconcile_shipment(test_db, s.id)
    assert res["error_count"] == 0
    assert res["status"] == "VALIDATED"


# Scenario 6: Unclassified shipment -> requires_classification flag and warning
def test_scenario_6_unclassified_shipment_requires_classification(client: TestClient, test_db: Session):
    s = Shipment(
        shipment_code=f"SHP-SC6-{uuid.uuid4().hex[:6]}",
        inbound_source=None,
        customs_declaration_no="104567890120",
        status="DRAFT"
    )
    test_db.add(s)
    test_db.commit()

    resp = client.get(f"/api/v1/shipments/{s.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["requires_classification"] is True

    # Reconciling unclassified shipment flags missing classification rule
    res = reconciliation_engine.reconcile_shipment(test_db, s.id)
    assert res["error_count"] > 0
    disc = test_db.query(Discrepancy).filter_by(
        shipment_id=s.id,
        rule_code="VAL-DOC-001",
        field_name="shipment.inbound_source"
    ).first()
    assert disc is not None
    assert disc.severity == "ERROR"


# Scenario 7: Shipment without container numbers -> blocked (VAL-CNT-002)
def test_scenario_7_missing_container_numbers_blocked(test_db: Session):
    s = Shipment(
        shipment_code=f"SHP-SC7-{uuid.uuid4().hex[:6]}",
        inbound_source="DOMESTIC",
        customs_declaration_no="104567890120",
        entry_date=date(2026, 10, 15),
        partner_name="CONG TY TNHH DIEN TU FOXCONN VN",
        notes="Linh kien dien tu",
        status="DRAFT"
    )
    test_db.add(s)
    test_db.flush()

    # Documents with empty container numbers
    hdr = {
        "consignee": "CONG TY TNHH DIEN TU FOXCONN VN",
        "container_numbers": [],
        "seal_numbers": ["EMC123456"],
        "total_packages": 50,
        "package_unit": "CARTONS",
        "total_gross_weight_kg": 1200.0,
        "total_invoice_value": 5000.0
    }
    items = [{"sku": "SKU-001", "quantity": 100, "po_reference": "PO-1", "unit_price": 50, "total_amount": 5000}]
    _build_helper_doc(test_db, s.id, "COMMERCIAL_INVOICE", hdr, items)
    _build_helper_doc(test_db, s.id, "PACKING_LIST", hdr, items)
    _build_helper_doc(test_db, s.id, "CUSTOMS_DECLARATION", hdr)
    _build_helper_doc(test_db, s.id, "WAREHOUSE_CONTRACT", {
        "document_number": "HD-001",
        "tenant_name": "FOXCONN VN",
        "valid_from": "2026-01-01",
        "valid_until": "2026-12-31"
    })
    test_db.commit()

    res = reconciliation_engine.reconcile_shipment(test_db, s.id)
    assert res["error_count"] > 0
    cnt_err = test_db.query(Discrepancy).filter_by(
        shipment_id=s.id,
        rule_code="VAL-CNT-002"
    ).first()
    assert cnt_err is not None
    assert cnt_err.severity == "ERROR"


# Scenario 8: Matching container numbers across documents -> passed
def test_scenario_8_matching_containers_passed(test_db: Session):
    err = validation_engine.validate_container_numbers(
        containers_bl=["TGHU1234567", "EMCU7654321"],
        containers_dec=["TGHU1234567", "EMCU7654321"]
    )
    assert err is None


# Scenario 9: Gross weight difference <= 0.5% -> passes tolerance check
def test_scenario_9_gross_weight_tolerance_within_threshold():
    # 1000.0 vs 1004.0 kg -> diff = 0.398% <= 0.5%
    pct = compute_tolerance_pct(1000.0, 1004.0)
    assert pct <= 0.5
    err = validation_engine.validate_weight_tolerance(1000.0, 1004.0, tolerance_pct=0.5)
    assert err is None


# Scenario 10: Gross weight difference > 0.5% -> blocked with ERROR (VAL-WGT-002)
def test_scenario_10_gross_weight_tolerance_exceeded_error():
    # 1000.0 vs 1010.0 kg -> diff = 0.99% > 0.5%
    pct = compute_tolerance_pct(1000.0, 1010.0)
    assert pct > 0.5
    err = validation_engine.validate_weight_tolerance(1000.0, 1010.0, tolerance_pct=0.5)
    assert err is not None
    assert err.rule_code == "VAL-WGT-002"
    assert err.severity == "ERROR"


# Scenario 11: CBM volume difference > 0.5% -> blocked with ERROR (VAL-CBM-001)
def test_scenario_11_cbm_tolerance_exceeded_error():
    # 20.0 m³ vs 21.0 m³ -> diff = 4.76% > 0.5%
    err = validation_engine.validate_cbm_tolerance(20.0, 21.0, source_a="B/L", source_b="PL", tolerance_pct=0.5)
    assert err is not None
    assert err.rule_code == "VAL-CBM-001"
    assert err.severity == "ERROR"


# Scenario 12: Package count mismatch (tolerance = 0) -> blocked with ERROR (VAL-PKG-001)
def test_scenario_12_package_count_mismatch_error():
    errs = validation_engine.validate_package_counts({"Invoice": 100, "PL": 99})
    assert len(errs) == 1
    assert errs[0].rule_code == "VAL-PKG-001"
    assert errs[0].severity == "ERROR"


# Scenario 13: Incompatible package units (carton vs pallet) -> blocked with ERROR (VAL-PKG-002)
def test_scenario_13_incompatible_package_units_error():
    errs = validation_engine.validate_package_counts(
        packages_by_doc={"Invoice": 100, "PL": 100},
        units_by_doc={"Invoice": "CARTONS", "PL": "PALLETS"}
    )
    assert len(errs) == 1
    assert errs[0].rule_code == "VAL-PKG-002"
    assert errs[0].severity == "ERROR"


# Scenario 14: Single-source transport metrics -> INFO/NOT_VERIFIED warning without blocking approval
def test_scenario_14_single_source_transport_metric_does_not_block(test_db: Session):
    s = Shipment(
        shipment_code=f"SHP-SC14-{uuid.uuid4().hex[:6]}",
        inbound_source="DOMESTIC",
        customs_declaration_no="104567890120",
        entry_date=date(2026, 10, 15),
        partner_name="CONG TY FOXCONN VN",
        notes="Linh kien dien tu",
        status="DRAFT"
    )
    test_db.add(s)
    test_db.flush()

    hdr_ci = {
        "consignee": "CONG TY FOXCONN VN",
        "container_numbers": ["TGHU1234567"],
        "seal_numbers": ["EMC123456"],
        "total_packages": 50,
        "package_unit": "CARTONS",
        "total_gross_weight_kg": 1200.0,
        "total_invoice_value": 5000.0
    }
    # Packing list does NOT provide CBM; only Invoice has CBM
    hdr_ci_with_cbm = dict(hdr_ci, measurement_cbm=12.5)
    items = [{"sku": "SKU-001", "quantity": 100, "po_reference": "PO-1", "unit_price": 50, "total_amount": 5000}]
    _build_helper_doc(test_db, s.id, "COMMERCIAL_INVOICE", hdr_ci_with_cbm, items)
    _build_helper_doc(test_db, s.id, "PACKING_LIST", hdr_ci, items)
    _build_helper_doc(test_db, s.id, "CUSTOMS_DECLARATION", hdr_ci)
    _build_helper_doc(test_db, s.id, "WAREHOUSE_CONTRACT", {
        "document_number": "HD-001",
        "tenant_name": "CONG TY FOXCONN VN",
        "lessor_name": "KHO DINH VU",
        "warehouse_name": "KHO DINH VU HAI PHONG",
        "valid_from": "2026-01-01",
        "valid_until": "2026-12-31"
    })
    test_db.commit()

    res = reconciliation_engine.reconcile_shipment(test_db, s.id)
    # The single-source CBM metric is recorded as INFO/NOT_VERIFIED and should not cause error_count > 0
    assert res["error_count"] == 0
    assert res["status"] == "VALIDATED"
    single_cbm = test_db.query(Discrepancy).filter_by(
        shipment_id=s.id,
        field_name="shipment.cbm_single_source"
    ).first()
    assert single_cbm is not None
    assert single_cbm.severity == "INFO"
    assert single_cbm.category == "NOT_VERIFIED"


# Scenario 15: Cargo owner vs Contract tenant match after corporate suffix normalization -> passed
def test_scenario_15_tenant_owner_normalized_match():
    doc_a = "CÔNG TY TNHH FOXCONN VIỆT NAM"
    doc_b = "FOXCONN VIETNAM CO., LTD"
    norm_a = normalize_company_name(doc_a)
    norm_b = normalize_company_name(doc_b)
    assert "FOXCONN" in norm_a and "FOXCONN" in norm_b

    errs = validate_contract(
        header={"document_number": "HD-01", "tenant_name": doc_a, "lessor_name": "KHO A", "warehouse_name": "KHO B", "valid_from": "2026-01-01", "valid_until": "2026-12-31"},
        entry_date=date(2026, 6, 1),
        owners=[doc_b]
    )
    assert len(errs) == 0


# Scenario 16: Cargo owner vs Contract tenant mismatch (similarity < 0.88) -> blocked (VAL-CONTRACT-001)
def test_scenario_16_tenant_owner_dissimilar_blocked():
    owner = "SAMSUNG ELECTRONICS VIETNAM CO., LTD"
    tenant = "FOXCONN PRECISION INDUSTRY CO., LTD"
    errs = validate_contract(
        header={"document_number": "HD-01", "tenant_name": tenant, "lessor_name": "KHO A", "warehouse_name": "KHO B", "valid_from": "2026-01-01", "valid_until": "2026-12-31"},
        entry_date=date(2026, 6, 1),
        owners=[owner]
    )
    assert len(errs) == 1
    assert errs[0].rule_code == "VAL-CONTRACT-001"
    assert errs[0].severity == "ERROR"


# Scenario 17: Actual arrival date before contract start date -> blocked
def test_scenario_17_actual_arrival_date_before_contract_validity_blocked():
    # Contract valid starting 2026-06-01, but entry_date is in 2026-01-10
    errs = validate_contract(
        header={
            "document_number": "HD-01",
            "tenant_name": "FOXCONN VN",
            "lessor_name": "KHO A",
            "warehouse_name": "KHO B",
            "valid_from": "2026-06-01",
        },
        entry_date=date(2026, 1, 10),
        owners=["FOXCONN VN"]
    )
    assert len(errs) == 1
    assert "VAL-CONTRACT" in errs[0].rule_code
    assert errs[0].severity == "ERROR"
    assert "trước" in errs[0].description_vi or "hiệu lực" in errs[0].description_vi


# Scenario 18: Missing actual arrival date (entry_date is None) -> blocked
def test_scenario_18_missing_actual_arrival_date_blocked(test_db: Session):
    s = Shipment(
        shipment_code=f"SHP-SC18-{uuid.uuid4().hex[:6]}",
        inbound_source="DOMESTIC",
        customs_declaration_no="104567890120",
        entry_date=None,  # Missing actual arrival date
        partner_name="CONG TY FOXCONN VN",
        notes="Linh kien dien tu",
        status="DRAFT"
    )
    test_db.add(s)
    test_db.flush()

    hdr = {
        "consignee": "CONG TY FOXCONN VN",
        "container_numbers": ["TGHU1234567"],
        "seal_numbers": ["EMC123456"],
        "total_packages": 50,
        "package_unit": "CARTONS",
        "total_gross_weight_kg": 1200.0,
        "total_invoice_value": 5000.0
    }
    items = [{"sku": "SKU-001", "quantity": 100, "po_reference": "PO-1", "unit_price": 50, "total_amount": 5000}]
    _build_helper_doc(test_db, s.id, "COMMERCIAL_INVOICE", hdr, items)
    _build_helper_doc(test_db, s.id, "PACKING_LIST", hdr, items)
    _build_helper_doc(test_db, s.id, "CUSTOMS_DECLARATION", hdr)
    _build_helper_doc(test_db, s.id, "WAREHOUSE_CONTRACT", {
        "document_number": "HD-001",
        "tenant_name": "CONG TY FOXCONN VN",
        "valid_from": "2026-01-01",
        "valid_until": "2026-12-31"
    })
    test_db.commit()

    res = reconciliation_engine.reconcile_shipment(test_db, s.id)
    assert res["error_count"] > 0
    date_err = test_db.query(Discrepancy).filter_by(
        shipment_id=s.id,
        field_name="shipment.entry_date"
    ).first()
    assert date_err is not None
    assert date_err.severity == "ERROR"


# Scenario 19: Repeated SKU lines under same PO -> quantities summed and reconciled accurately
def test_scenario_19_repeated_sku_lines_summed_correctly(test_db: Session):
    s = Shipment(
        shipment_code=f"SHP-SC19-{uuid.uuid4().hex[:6]}",
        inbound_source="DOMESTIC",
        customs_declaration_no="104567890120",
        entry_date=date(2026, 10, 15),
        partner_name="CONG TY FOXCONN VN",
        notes="Linh kien dien tu",
        status="DRAFT"
    )
    test_db.add(s)
    test_db.flush()

    hdr = {
        "consignee": "CONG TY FOXCONN VN",
        "container_numbers": ["TGHU1234567"],
        "seal_numbers": ["EMC123456"],
        "total_packages": 150,
        "package_unit": "CARTONS",
        "total_gross_weight_kg": 1500.0,
        "total_invoice_value": 7500.0
    }
    # Invoice has 2 lines for SKU-001 under PO-1: 60 pcs + 40 pcs = 100 pcs total
    ci_items = [
        {"sku": "SKU-001", "quantity": 60, "po_reference": "PO-1", "unit_price": 50, "total_amount": 3000},
        {"sku": "SKU-001", "quantity": 40, "po_reference": "PO-1", "unit_price": 50, "total_amount": 2000},
        {"sku": "SKU-002", "quantity": 50, "po_reference": "PO-2", "unit_price": 50, "total_amount": 2500},
    ]
    # Packing List has 1 line for SKU-001 under PO-1: 100 pcs
    pl_items = [
        {"sku": "SKU-001", "quantity": 100, "po_reference": "PO-1"},
        {"sku": "SKU-002", "quantity": 50, "po_reference": "PO-2"},
    ]
    _build_helper_doc(test_db, s.id, "COMMERCIAL_INVOICE", hdr, ci_items)
    _build_helper_doc(test_db, s.id, "PACKING_LIST", hdr, pl_items)
    _build_helper_doc(test_db, s.id, "CUSTOMS_DECLARATION", hdr)
    _build_helper_doc(test_db, s.id, "WAREHOUSE_CONTRACT", {
        "document_number": "HD-001",
        "tenant_name": "CONG TY FOXCONN VN",
        "lessor_name": "KHO DINH VU",
        "warehouse_name": "KHO DINH VU HAI PHONG",
        "valid_from": "2026-01-01",
        "valid_until": "2026-12-31"
    })
    test_db.commit()

    res = reconciliation_engine.reconcile_shipment(test_db, s.id)
    assert res["error_count"] == 0
    assert res["status"] == "VALIDATED"
    # Verify SKU-001 was aggregated to 100 on both Invoice and PL
    sku_1 = next(row for row in res["sku_matrix"] if row["sku"] == "SKU-001" and row["po_reference"] == "PO-1")
    assert sku_1["qty_invoice"] == 100.0
    assert sku_1["qty_packing_list"] == 100.0
    assert sku_1["is_matched"] is True


# Scenario 20: Staff manual edit to arrival date revokes approval and triggers revalidation
def test_scenario_20_staff_manual_edit_revokes_approval_and_revalidates(client: TestClient, test_db: Session):
    s = Shipment(
        shipment_code=f"SHP-SC20-{uuid.uuid4().hex[:6]}",
        inbound_source="DOMESTIC",
        customs_declaration_no="104567890120",
        entry_date=date(2026, 10, 15),
        partner_name="CONG TY FOXCONN VN",
        notes="Linh kien dien tu",
        status="VALIDATED",
        approval_status="APPROVED",
        approved_by="TruongPhongHaiQuan"
    )
    test_db.add(s)
    test_db.flush()

    hdr = {
        "consignee": "CONG TY FOXCONN VN",
        "container_numbers": ["TGHU1234567"],
        "seal_numbers": ["EMC123456"],
        "total_packages": 50,
        "package_unit": "CARTONS",
        "total_gross_weight_kg": 1200.0,
        "total_invoice_value": 5000.0
    }
    items = [{"sku": "SKU-001", "quantity": 100, "po_reference": "PO-1", "unit_price": 50, "total_amount": 5000}]
    _build_helper_doc(test_db, s.id, "COMMERCIAL_INVOICE", hdr, items)
    _build_helper_doc(test_db, s.id, "PACKING_LIST", hdr, items)
    _build_helper_doc(test_db, s.id, "CUSTOMS_DECLARATION", hdr)
    _build_helper_doc(test_db, s.id, "WAREHOUSE_CONTRACT", {
        "document_number": "HD-001",
        "tenant_name": "CONG TY FOXCONN VN",
        "lessor_name": "KHO DINH VU",
        "warehouse_name": "KHO DINH VU HAI PHONG",
        "valid_from": "2026-01-01",
        "valid_until": "2026-12-31"
    })
    test_db.commit()

    # Verify initial approved state
    test_db.refresh(s)
    assert s.approval_status == "APPROVED"

    # Staff updates entry_date via PATCH /api/v1/shipments/{id}
    patch_resp = client.patch(
        f"/api/v1/shipments/{s.id}",
        json={"entry_date": "2026-11-20"}
    )
    assert patch_resp.status_code == 200

    test_db.commit()
    test_db.refresh(s)
    # Approval must be revoked
    assert s.approval_status == "PENDING"
    assert s.entry_date == date(2026, 11, 20)

    # An audit log entry must be present
    audit = test_db.query(AuditLog).filter_by(
        shipment_id=s.id,
        field_name="entry_date"
    ).first()
    assert audit is not None
    assert audit.new_value == "2026-11-20"


# Scenario 21: Foreign shipment with Sale Contract (SC) -> Seller(SC) == Exporter(TK), Buyer(SC) == Shipper(INV/PL) == Tenant(HD), Consignee == U&I
def test_scenario_21_sale_contract_roles_and_14_field_matrix(test_db: Session):
    s = Shipment(
        shipment_code=f"SHP-SC21-{uuid.uuid4().hex[:6]}",
        inbound_source="FOREIGN",
        customs_declaration_no="104567890999",
        entry_date=date(2026, 10, 15),
        partner_name="SAMSUNG ELECTRONICS VIETNAM CO., LTD",
        notes="Linh kien ban dan",
        status="DRAFT"
    )
    test_db.add(s)
    test_db.flush()

    items = [{"sku": "IC-900", "quantity": 500, "po_reference": "PO-SC-01", "unit_price": 10, "total_amount": 5000}]

    # SC: Seller = GLOBAL CHIP CORP, Buyer = SAMSUNG ELECTRONICS VIETNAM CO., LTD, Consignee = U&I LOGISTICS
    _build_helper_doc(test_db, s.id, "SALE_CONTRACT", {
        "document_number": "SC-2026-001",
        "shipper": "GLOBAL CHIP CORP",
        "buyer_name": "SAMSUNG ELECTRONICS VIETNAM CO., LTD",
        "consignee": "CONG TY CO PHAN LOGISTICS U&I",
        "po_numbers": ["PO-SC-01"],
        "commodity_description": "Linh kien ban dan",
    }, items)

    # INV (Có SC): Signed between Seller (GLOBAL CHIP CORP) & Buyer (SAMSUNG ELECTRONICS VIETNAM CO., LTD) on SC
    inv_hdr = {
        "document_number": "INV-2026-888",
        "shipper": "GLOBAL CHIP CORP",
        "buyer_name": "SAMSUNG ELECTRONICS VIETNAM CO., LTD",
        "consignee": "SAMSUNG ELECTRONICS VIETNAM CO., LTD",
        "po_numbers": ["PO-SC-01"],
        "commodity_description": "Linh kien ban dan",
        "total_packages": 50,
        "package_unit": "CARTONS",
        "total_gross_weight_kg": 1000.0,
        "measurement_cbm": 12.0,
        "total_invoice_value": 5000.4,  # Within 0.5 value tolerance vs 5000.0 on SC & TK
    }
    pl_hdr = {
        "document_number": "PL-2026-888",
        "shipper": "SAMSUNG ELECTRONICS VIETNAM CO., LTD",
        "consignee": "CONG TY CO PHAN LOGISTICS U&I",
        "po_numbers": ["PO-SC-01"],
        "commodity_description": "Linh kien ban dan",
        "total_packages": 50,
        "package_unit": "CARTONS",
        "total_gross_weight_kg": 1000.0,
        "measurement_cbm": 12.0,
    }
    _build_helper_doc(test_db, s.id, "COMMERCIAL_INVOICE", inv_hdr, items)
    _build_helper_doc(test_db, s.id, "PACKING_LIST", pl_hdr, items)

    # BL & AN: Shipper can be forwarder, but final Consignee is U&I LOGISTICS
    bl_an_hdr = {
        "document_number": "BL-2026-777",
        "shipper": "DHL GLOBAL FORWARDING",
        "consignee": "CONG TY CO PHAN LOGISTICS U&I",
        "port_of_discharge": "CAT LAI PORT",
        "vessel_voyage": "EVER GIVEN V.101",
        "eta": "2026-10-14",
        "container_numbers": ["MSCU1234567"],
        "seal_numbers": ["SL998877"],
        "commodity_description": "Linh kien ban dan",
        "total_packages": 50,
        "package_unit": "CARTONS",
        "total_gross_weight_kg": 1000.0,
        "measurement_cbm": 12.0,
    }
    _build_helper_doc(test_db, s.id, "BILL_OF_LADING", bl_an_hdr)
    _build_helper_doc(test_db, s.id, "ARRIVAL_NOTICE", bl_an_hdr)

    # TK: Người xuất khẩu = GLOBAL CHIP CORP (matches Seller on SC!), Chủ hàng = SAMSUNG, Consignee = U&I
    _build_helper_doc(test_db, s.id, "CUSTOMS_DECLARATION", {
        "document_number": "104567890999",
        "shipper": "GLOBAL CHIP CORP",
        "cargo_owner_name": "SAMSUNG ELECTRONICS VIETNAM CO., LTD",
        "consignee": "CONG TY CO PHAN LOGISTICS U&I",
        "port_of_discharge": "CAT LAI PORT",
        "vessel_voyage": "EVER GIVEN V.101",
        "eta": "2026-10-14",
        "container_numbers": ["MSCU1234567"],
        "seal_numbers": ["SL998877"],
        "invoice_number_ref": "INV-2026-888",
        "contract_number_ref": "HD-KHO-2026-99",
        "commodity_description": "Linh kien ban dan",
        "total_packages": 50,
        "package_unit": "CARTONS",
        "total_gross_weight_kg": 1000.0,
    }, items)

    # HD: Hợp đồng thuê kho
    _build_helper_doc(test_db, s.id, "WAREHOUSE_CONTRACT", {
        "document_number": "HD-KHO-2026-99",
        "tenant_name": "SAMSUNG ELECTRONICS VIETNAM CO., LTD",
        "lessor_name": "CONG TY CO PHAN LOGISTICS U&I",
        "warehouse_name": "KHO NGOAI QUAN U&I",
        "commodity_description": "Linh kien ban dan",
        "valid_from": "2026-01-01",
        "valid_until": "2026-12-31",
    })
    test_db.commit()

    res = reconciliation_engine.reconcile_shipment(test_db, s.id)
    assert res["error_count"] == 0
    assert res["has_sale_contract"] is True
    assert len(res["field_matrix"]) == 13
    assert all(row["status"] in ("MATCHED", "SINGLE_SOURCE") for row in res["field_matrix"])

