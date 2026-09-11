import json
import sqlite3
from datetime import datetime
from typing import Literal

from legalintel.models.matter import Matter, MatterDocument
from legalintel.storage import connect as _connect


def _row_to_matter(row: sqlite3.Row) -> Matter:
    return Matter(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        created_by=row["created_by"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


# Matter has no `organization_id` field on the pydantic model itself - that's an
# internal scoping detail (see storage.py), not something callers of Matter need to
# see once it's already been filtered by the functions below.


def _row_to_matter_document(row: sqlite3.Row) -> MatterDocument:
    return MatterDocument(
        id=row["id"],
        matter_id=row["matter_id"],
        source_filename=row["source_filename"],
        analysis_type=row["analysis_type"],
        result=json.loads(row["result_json"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def add_matter(
    db_path: str, *, name: str, description: str | None, organization_id: int, created_by: int | None = None
) -> Matter:
    created_at = datetime.now().astimezone().isoformat()
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO matters (name, description, organization_id, created_by, created_at) VALUES (?, ?, ?, ?, ?)",
            (name, description, organization_id, created_by, created_at),
        )
        row = conn.execute("SELECT * FROM matters WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _row_to_matter(row)


def get_matter(db_path: str, matter_id: int, *, organization_id: int) -> Matter | None:
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM matters WHERE id = ? AND organization_id = ?", (matter_id, organization_id)
        ).fetchone()
    return _row_to_matter(row) if row is not None else None


def list_matters(db_path: str, *, organization_id: int) -> list[Matter]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM matters WHERE organization_id = ? ORDER BY id", (organization_id,)
        ).fetchall()
    return [_row_to_matter(row) for row in rows]


def delete_matter(db_path: str, matter_id: int, *, organization_id: int) -> bool:
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT id FROM matters WHERE id = ? AND organization_id = ?", (matter_id, organization_id)
        ).fetchone()
        if row is None:
            return False

        docket_ids = [
            r["id"] for r in conn.execute("SELECT id FROM tracked_dockets WHERE matter_id = ?", (matter_id,))
        ]
        doc_ids = [
            r["id"] for r in conn.execute("SELECT id FROM matter_documents WHERE matter_id = ?", (matter_id,))
        ]

        for docket_id in docket_ids:
            conn.execute("DELETE FROM docket_alerts WHERE tracked_docket_id = ?", (docket_id,))
            conn.execute("DELETE FROM seen_docket_entries WHERE tracked_docket_id = ?", (docket_id,))
        conn.execute("DELETE FROM tracked_dockets WHERE matter_id = ?", (matter_id,))

        for doc_id in doc_ids:
            conn.execute("DELETE FROM clause_reviews WHERE matter_document_id = ?", (doc_id,))
        conn.execute("DELETE FROM matter_documents WHERE matter_id = ?", (matter_id,))

        conn.execute("DELETE FROM matters WHERE id = ?", (matter_id,))
        return True


def add_matter_document(
    db_path: str,
    *,
    matter_id: int,
    source_filename: str,
    analysis_type: Literal["parse", "extract_clauses", "classify"],
    result: dict,
) -> MatterDocument:
    created_at = datetime.now().astimezone().isoformat()
    with _connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO matter_documents
                (matter_id, source_filename, analysis_type, result_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (matter_id, source_filename, analysis_type, json.dumps(result), created_at),
        )
        row = conn.execute("SELECT * FROM matter_documents WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _row_to_matter_document(row)


def get_matter_document(db_path: str, document_id: int) -> MatterDocument | None:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM matter_documents WHERE id = ?", (document_id,)).fetchone()
    return _row_to_matter_document(row) if row is not None else None


def list_matter_documents(db_path: str, matter_id: int) -> list[MatterDocument]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM matter_documents WHERE matter_id = ? ORDER BY id", (matter_id,)
        ).fetchall()
    return [_row_to_matter_document(row) for row in rows]


def list_all_matter_documents(db_path: str, *, organization_id: int) -> list[MatterDocument]:
    # matter_documents has no organization_id column of its own (see storage.py) -
    # scope via a join through its parent matter instead.
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT matter_documents.* FROM matter_documents
            JOIN matters ON matters.id = matter_documents.matter_id
            WHERE matters.organization_id = ?
            ORDER BY matter_documents.id
            """,
            (organization_id,),
        ).fetchall()
    return [_row_to_matter_document(row) for row in rows]
