from sqlalchemy import Engine, inspect, text

from app.db.session import engine as default_engine
from app.db.base import Base
import app.models  # noqa: F401

_DOCUMENTS_DDL = """
CREATE TABLE documents_new (
    id VARCHAR(36) NOT NULL,
    shipment_id VARCHAR(36),
    original_filename VARCHAR(255) NOT NULL,
    storage_path VARCHAR(512) NOT NULL,
    mime_type VARCHAR(128) NOT NULL,
    sha256_hash VARCHAR(64) NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    page_count INTEGER,
    document_type VARCHAR(64),
    parsed_content_json TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    uploaded_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(shipment_id) REFERENCES shipments (id),
    UNIQUE (storage_path)
)
"""


def migrate_documents_table(bind: Engine = default_engine) -> None:
    """Additive/rebuild SQLite migration for databases created before Phase 2.

    create_all() never alters existing tables. Phase 1 created `documents` with
    `page_count NOT NULL` and `file_size`; Phase 2 needs nullable page_count (Excel
    has no pages), `file_size_bytes`, `parsed_content_json` and `version`.
    SQLite cannot relax NOT NULL via ALTER, so the table is rebuilt, preserving rows.
    """
    inspector = inspect(bind)
    if "documents" not in inspector.get_table_names():
        return
    info = {c["name"]: c for c in inspector.get_columns("documents")}

    if info["page_count"]["nullable"] is False:
        size_src = "file_size_bytes" if "file_size_bytes" in info else "file_size"
        parsed_src = "parsed_content_json" if "parsed_content_json" in info else "NULL"
        version_src = "version" if "version" in info else "1"
        # DDL/PRAGMA need autocommit; foreign keys off so the swap does not cascade.
        with bind.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text("PRAGMA foreign_keys=OFF"))
            try:
                conn.execute(text("DROP TABLE IF EXISTS documents_new"))
                conn.execute(text(_DOCUMENTS_DDL))
                conn.execute(text(
                    "INSERT INTO documents_new (id, shipment_id, original_filename, storage_path, mime_type, "
                    "sha256_hash, file_size_bytes, page_count, document_type, parsed_content_json, version, uploaded_at) "
                    f"SELECT id, shipment_id, original_filename, storage_path, mime_type, sha256_hash, {size_src}, "
                    f"page_count, document_type, {parsed_src}, {version_src}, uploaded_at FROM documents"
                ))
                conn.execute(text("DROP TABLE documents"))
                conn.execute(text("ALTER TABLE documents_new RENAME TO documents"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_documents_shipment_id ON documents (shipment_id)"))
            finally:
                conn.execute(text("PRAGMA foreign_keys=ON"))
        return

    with bind.begin() as conn:
        if "file_size" in info and "file_size_bytes" not in info:
            conn.execute(text("ALTER TABLE documents RENAME COLUMN file_size TO file_size_bytes"))
        if "parsed_content_json" not in info:
            conn.execute(text("ALTER TABLE documents ADD COLUMN parsed_content_json TEXT"))
        if "version" not in info:
            conn.execute(text("ALTER TABLE documents ADD COLUMN version INTEGER NOT NULL DEFAULT 1"))

    # Extractions & Line items table migration
    if "document_extractions" in inspector.get_table_names():
        ext_cols = {c["name"] for c in inspector.get_columns("document_extractions")}
        with bind.begin() as conn:
            if "prompt_tokens" not in ext_cols:
                conn.execute(text("ALTER TABLE document_extractions ADD COLUMN prompt_tokens INTEGER"))
            if "candidate_tokens" not in ext_cols:
                conn.execute(text("ALTER TABLE document_extractions ADD COLUMN candidate_tokens INTEGER"))

    if "extracted_line_items" in inspector.get_table_names():
        li_cols = {c["name"] for c in inspector.get_columns("extracted_line_items")}
        with bind.begin() as conn:
            if "raw_line_text" not in li_cols:
                conn.execute(text("ALTER TABLE extracted_line_items ADD COLUMN raw_line_text TEXT"))

    # Discrepancies category column migration
    if "discrepancies" in inspector.get_table_names():
        disc_cols = {c["name"] for c in inspector.get_columns("discrepancies")}
        with bind.begin() as conn:
            if "category" not in disc_cols:
                conn.execute(text("ALTER TABLE discrepancies ADD COLUMN category VARCHAR(32) DEFAULT 'CONFLICT'"))


def init_db() -> None:
    """Create all SQLite tables if they do not exist."""
    print("Initializing database tables for Vietnamese Bonded Warehouse AI...")
    Base.metadata.create_all(bind=default_engine)
    migrate_documents_table(default_engine)
    columns = {c["name"] for c in inspect(default_engine).get_columns("shipments")}
    if "entry_date" not in columns:
        with default_engine.begin() as connection:
            connection.execute(text("ALTER TABLE shipments ADD COLUMN entry_date DATE"))

    # Preserve legacy rows while allowing an unknown quantity to remain NULL.
    line_columns = {c["name"]: c for c in inspect(default_engine).get_columns("extracted_line_items")}
    if not line_columns["quantity"]["nullable"]:
        import re
        with default_engine.begin() as connection:
            ddl = connection.execute(text("SELECT sql FROM sqlite_master WHERE type='table' AND name='extracted_line_items'")).scalar_one()
            indexes = connection.execute(text("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='extracted_line_items' AND sql IS NOT NULL")).scalars().all()
            ddl = ddl.replace("CREATE TABLE extracted_line_items", "CREATE TABLE extracted_line_items_nullable", 1)
            ddl = re.sub(r"quantity FLOAT NOT NULL", "quantity FLOAT", ddl)
            connection.execute(text(ddl))
            columns_sql = ", ".join('"' + name + '"' for name in line_columns)
            connection.execute(text(f"INSERT INTO extracted_line_items_nullable ({columns_sql}) SELECT {columns_sql} FROM extracted_line_items"))
            connection.execute(text("DROP TABLE extracted_line_items"))
            connection.execute(text("ALTER TABLE extracted_line_items_nullable RENAME TO extracted_line_items"))
            for index_sql in indexes:
                connection.execute(text(index_sql))

    from app.db.session import SessionLocal
    from app.services.validation.config import seed_default_rules
    db = SessionLocal()
    try:
        seed_default_rules(db)
    finally:
        db.close()

    print("Database tables initialized successfully.")


if __name__ == "__main__":
    init_db()
