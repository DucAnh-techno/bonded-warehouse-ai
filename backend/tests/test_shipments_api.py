import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import get_db

client = TestClient(app)


def test_create_and_get_shipment():
    payload = {
        "shipment_code": "SHP-2026-TEST-01",
        "customs_declaration_no": "100234567890",
        "declaration_type": "C11",
        "warehouse_type": "BONDED",
        "bonded_warehouse_name": "Kho Ngoại Quan Đình Vũ - Hải Phòng",
        "partner_name": "Hanoi Hi-Tech JSC",
        "direction": "INBOUND",
        "notes": "Lô hàng thử nghiệm Phase 1"
    }

    # 1. Create shipment
    response = client.post("/api/v1/shipments/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["shipment_code"] == "SHP-2026-TEST-01"
    assert data["status"] == "DRAFT"
    assert data["direction"] == "INBOUND"
    shipment_id = data["id"]

    # 2. Get shipment by ID
    get_res = client.get(f"/api/v1/shipments/{shipment_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == shipment_id
    assert get_res.json()["partner_name"] == "Hanoi Hi-Tech JSC"

    # 3. Prevent duplicate shipment code
    dup_res = client.post("/api/v1/shipments/", json=payload)
    assert dup_res.status_code == 400
    assert "đã tồn tại" in dup_res.json()["detail"]


def test_list_and_filter_shipments():
    # Create another shipment
    payload = {
        "shipment_code": "SHP-2026-TEST-OUT-02",
        "customs_declaration_no": "200987654321",
        "declaration_type": "C21",
        "direction": "OUTBOUND",
        "partner_name": "Samsung Electronics Vietnam"
    }
    client.post("/api/v1/shipments/", json=payload)

    # List all
    res = client.get("/api/v1/shipments/")
    assert res.status_code == 200
    items = res.json()
    assert len(items) >= 2

    # Filter by direction
    inbound_res = client.get("/api/v1/shipments/?direction=INBOUND")
    assert inbound_res.status_code == 200
    for s in inbound_res.json():
        assert s["direction"] == "INBOUND"

    # Search by code or declaration
    search_res = client.get("/api/v1/shipments/?search=200987")
    assert search_res.status_code == 200
    assert len(search_res.json()) >= 1
    assert search_res.json()[0]["customs_declaration_no"] == "200987654321"


def test_statistics_summary():
    stats_res = client.get("/api/v1/shipments/statistics/summary")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["total_shipments"] >= 2
    assert "inbound_count" in stats
    assert "outbound_count" in stats
