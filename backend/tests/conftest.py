import os
import pathlib
import pytest
import json
import uuid
from datetime import date
from fastapi.testclient import TestClient

# Use a dedicated test SQLite database file.
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["DEBUG"] = "false"
os.environ["DEMO_ONLY"] = "false"
import tempfile
_upload_test_dir = tempfile.TemporaryDirectory(prefix="bonded-tests-")
os.environ["UPLOAD_DIR"] = _upload_test_dir.name

# Import after setting env var so settings picks up the test DB URL.
# Import the FastAPI instance as 'fastapi_app' to avoid shadowing the 'app' package.
from app.main import app as fastapi_app
from app.db.session import SessionLocal, engine
import app.models  # Ensure all models are imported so metadata is registered.
from app.db.base import Base

# Initialize the database schema.

def _init_db() -> None:
    """Create tables in a fresh test SQLite database, removing any existing file."""
    import pathlib
    db_path = pathlib.Path("./test.db")
    if db_path.exists():
        try:
            db_path.unlink()
        except Exception:
            pass
    Base.metadata.create_all(bind=engine)

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Create tables once for the test session and clean up afterwards."""
    _init_db()
    yield
    # Close all connections and remove the test DB file.
    try:
        SessionLocal().close()
    except Exception:
        pass
    engine.dispose()
    db_path = pathlib.Path("./test.db")
    if db_path.exists():
        db_path.unlink()

@pytest.fixture(scope="function")
def test_db():
    """Provide a fresh SQLAlchemy session for each test function."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(scope="function")
def client(test_db):
    """FastAPI test client that uses the same DB session."""
    # Override the get_db dependency to return the test session.
    from app.db.session import get_db as original_get_db
    def _override_get_db():
        try:
            yield test_db
        finally:
            pass
    fastapi_app.dependency_overrides[original_get_db] = _override_get_db
    with TestClient(fastapi_app) as c:
        yield c
    # Clean up override.
    fastapi_app.dependency_overrides.pop(original_get_db, None)


def complete_demo_fixture(db, shipment):
    """Explicitly complete legacy valid fixtures with the newly required Invoice/PL/Lease/Declaration."""
    from app.models.document import Document
    from app.models.extraction import DocumentExtraction, ExtractedLineItem
    shipment.entry_date = date(2026, 10, 11)
    if not shipment.inbound_source:
        shipment.inbound_source = "DOMESTIC"
    if not shipment.customs_declaration_no:
        shipment.customs_declaration_no = "104567890120"

    docs = db.query(Document).filter_by(shipment_id=shipment.id).all()
    invoice = next((d for d in docs if d.document_type == "COMMERCIAL_INVOICE"), None)
    if invoice is None:
        invoice = next((d for d in docs if d.document_type == "CUSTOMS_DECLARATION"), None)
        if invoice is not None:
            invoice.document_type = "COMMERCIAL_INVOICE"

    def make_doc(dtype):
        doc = Document(shipment_id=shipment.id, document_type=dtype, original_filename=dtype+'.pdf',
            storage_path=uuid.uuid4().hex+'.pdf', mime_type='application/pdf', file_size_bytes=1, sha256_hash='test')
        db.add(doc); db.flush()
        doc.extraction = DocumentExtraction(document_id=doc.id, status='SUCCESS', model_name='test', raw_response_json='{}')
        db.flush()
        return doc

    if invoice is None:
        invoice = make_doc('COMMERCIAL_INVOICE')
        invoice.extraction.line_items.append(ExtractedLineItem(sku='0001', description_vi='Sample', quantity=2, uom='PCS', unit_price=3, total_amount=6))
    db.flush()

    packing = next((d for d in docs if d.document_type == 'PACKING_LIST'), None)
    if packing is None:
        packing = make_doc('PACKING_LIST')
        for item in invoice.extraction.line_items:
            packing.extraction.line_items.append(ExtractedLineItem(sku=item.sku, part_number=item.part_number,
                description_vi=item.description_vi, quantity=item.quantity, uom=item.uom, po_reference=item.po_reference, hs_code=item.hs_code))

    customs = next((d for d in docs if d.document_type == 'CUSTOMS_DECLARATION'), None)
    if customs is None:
        customs = make_doc('CUSTOMS_DECLARATION')
        for item in invoice.extraction.line_items:
            customs.extraction.line_items.append(ExtractedLineItem(sku=item.sku, part_number=item.part_number,
                description_vi=item.description_vi, quantity=item.quantity, uom=item.uom, po_reference=item.po_reference, hs_code=item.hs_code))

    docs = db.query(Document).filter_by(shipment_id=shipment.id).all()
    if not shipment.partner_name:
        shipment.partner_name = "DEMO TENANT"
    if not shipment.notes:
        shipment.notes = "Sample commodity description"

    target_gw = 12.0
    target_pkg = 12
    target_pkg_unit = "CARTONS"
    for d in docs:
        if d.extraction and d.extraction.extracted_header_json:
            h = json.loads(d.extraction.extracted_header_json)
            if h.get('total_gross_weight_kg'):
                target_gw = float(h['total_gross_weight_kg'])
            if h.get('total_packages'):
                try:
                    target_pkg = int(h['total_packages'])
                except Exception:
                    pass
            if h.get('package_unit'):
                target_pkg_unit = str(h['package_unit'])

    for doc in docs:
        if doc.extraction:
            header = json.loads(doc.extraction.extracted_header_json or '{}')
            header.pop('shipper', None)
            header['consignee'] = 'DEMO TENANT'
            header['container_numbers'] = ['TGHU1234567']
            header['seal_numbers'] = ['EMC123456']
            header['total_packages'] = target_pkg
            header['package_unit'] = target_pkg_unit
            header['total_gross_weight_kg'] = target_gw
            if header.get('total_net_weight_kg') and float(header['total_net_weight_kg']) > target_gw:
                header['total_net_weight_kg'] = target_gw * 0.9
            header.setdefault('measurement_cbm', 1.5)
            if doc.document_type == 'COMMERCIAL_INVOICE':
                header['total_invoice_value'] = sum(item.total_amount or 0 for item in doc.extraction.line_items)
            if doc.document_type == 'CUSTOMS_DECLARATION':
                header['document_number'] = shipment.customs_declaration_no
            doc.extraction.extracted_header_json = json.dumps(header)

    contract = next((d for d in docs if d.document_type == 'WAREHOUSE_CONTRACT'), None)
    if contract is None:
        contract = make_doc('WAREHOUSE_CONTRACT')
    contract.extraction.extracted_header_json = json.dumps(dict(document_number='LEASE-0001', tenant_name='DEMO TENANT',
        lessor_name='DEMO LESSOR', warehouse_name='DEMO WAREHOUSE', valid_from='2026-01-01', valid_until='2026-12-31'))

    db.commit()
    return invoice, packing, contract
