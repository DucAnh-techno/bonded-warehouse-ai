"""Migration of a legacy Phase-1 `documents` table (NOT NULL page_count, file_size)."""
import sqlite3

from sqlalchemy import create_engine, inspect

from app.db.init_db import migrate_documents_table


def test_legacy_documents_table_is_rebuilt_and_rows_preserved(tmp_path):
    db = tmp_path / "legacy.db"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE shipments (id VARCHAR(36) PRIMARY KEY);
        CREATE TABLE documents (
            id VARCHAR(36) PRIMARY KEY, shipment_id VARCHAR(36), original_filename VARCHAR(255) NOT NULL,
            storage_path VARCHAR(512) NOT NULL UNIQUE, mime_type VARCHAR(128) NOT NULL,
            sha256_hash VARCHAR(64) NOT NULL, file_size INTEGER NOT NULL, page_count INTEGER NOT NULL,
            document_type VARCHAR(64), uploaded_at DATETIME NOT NULL,
            FOREIGN KEY(shipment_id) REFERENCES shipments (id));
        INSERT INTO shipments VALUES ('s1');
        INSERT INTO documents VALUES ('d1','s1','a.pdf','p1','application/pdf','h',123,2,'OTHER','2026-01-01');
        """
    )
    con.commit()
    con.close()

    eng = create_engine(f"sqlite:///{db.as_posix()}")
    migrate_documents_table(eng)
    migrate_documents_table(eng)  # idempotent

    cols = {c["name"]: c for c in inspect(eng).get_columns("documents")}
    assert cols["page_count"]["nullable"] is True
    assert {"file_size_bytes", "parsed_content_json", "version"} <= set(cols)
    with eng.connect() as c:
        row = c.exec_driver_sql(
            "SELECT id, file_size_bytes, page_count, version FROM documents"
        ).one()
        assert tuple(row) == ("d1", 123, 2, 1)
        c.exec_driver_sql(  # Excel row without page count is now accepted
            "INSERT INTO documents (id, original_filename, storage_path, mime_type, sha256_hash, "
            "file_size_bytes, uploaded_at) VALUES ('d2','b.xls','p2','x','h',1,'2026-01-01')"
        )
    eng.dispose()
