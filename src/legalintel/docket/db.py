import json
import sqlite3
from datetime import datetime

from legalintel.models.docket import DocketAlert, DocketEntry, TrackedDocket
from legalintel.storage import connect as _connect
from legalintel.storage import init_db  # noqa: F401 - re-exported for callers of legalintel.docket.db


def _row_to_tracked_docket(row: sqlite3.Row) -> TrackedDocket:
    return TrackedDocket(
        id=row["id"],
        courtlistener_docket_id=row["courtlistener_docket_id"],
        court=row["court"],
        docket_number=row["docket_number"],
        case_name=row["case_name"],
        matter_id=row["matter_id"],
        created_at=datetime.fromisoformat(row["created_at"]),
        last_checked_at=datetime.fromisoformat(row["last_checked_at"]) if row["last_checked_at"] else None,
    )


def _row_to_alert(row: sqlite3.Row) -> DocketAlert:
    return DocketAlert(
        id=row["id"],
        tracked_docket_id=row["tracked_docket_id"],
        created_at=datetime.fromisoformat(row["created_at"]),
        new_entry_count=row["new_entry_count"],
        new_entry_ids=json.loads(row["new_entry_ids"]),
    )


def add_tracked_docket(
    db_path: str,
    *,
    courtlistener_docket_id: int,
    court: str | None,
    docket_number: str | None,
    case_name: str | None,
    matter_id: int | None,
    organization_id: int,
) -> TrackedDocket:
    created_at = datetime.now().astimezone().isoformat()
    with _connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO tracked_dockets
                (courtlistener_docket_id, court, docket_number, case_name, matter_id, organization_id,
                 created_at, last_checked_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (courtlistener_docket_id, court, docket_number, case_name, matter_id, organization_id, created_at),
        )
        row = conn.execute("SELECT * FROM tracked_dockets WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _row_to_tracked_docket(row)


def get_tracked_docket(db_path: str, tracked_docket_id: int, *, organization_id: int) -> TrackedDocket | None:
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM tracked_dockets WHERE id = ? AND organization_id = ?",
            (tracked_docket_id, organization_id),
        ).fetchone()
    return _row_to_tracked_docket(row) if row is not None else None


def get_tracked_docket_by_courtlistener_id(db_path: str, courtlistener_docket_id: int) -> TrackedDocket | None:
    """Deliberately NOT organization-scoped, unlike every other lookup in this
    module. `courtlistener_docket_id` carries a table-wide UNIQUE constraint (see
    storage.py) - a real-world docket can currently only be tracked by one
    organization platform-wide. Making this per-org would need a composite unique
    constraint, which SQLite can't add without a full table rebuild (this repo's
    stated policy is not to introduce that migration machinery). Accepted as a known
    Phase 1 limitation rather than silently producing a 500 (IntegrityError) if this
    were scoped and a second org tried to track an already-tracked docket."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM tracked_dockets WHERE courtlistener_docket_id = ?", (courtlistener_docket_id,)
        ).fetchone()
    return _row_to_tracked_docket(row) if row is not None else None


def list_tracked_dockets(db_path: str, *, organization_id: int) -> list[TrackedDocket]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM tracked_dockets WHERE organization_id = ? ORDER BY id", (organization_id,)
        ).fetchall()
    return [_row_to_tracked_docket(row) for row in rows]


def list_tracked_dockets_for_matter(db_path: str, matter_id: int, *, organization_id: int) -> list[TrackedDocket]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM tracked_dockets WHERE matter_id = ? AND organization_id = ? ORDER BY id",
            (matter_id, organization_id),
        ).fetchall()
    return [_row_to_tracked_docket(row) for row in rows]


def get_seen_entry_ids(db_path: str, tracked_docket_id: int) -> set[int]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT courtlistener_entry_id FROM seen_docket_entries WHERE tracked_docket_id = ?",
            (tracked_docket_id,),
        ).fetchall()
    return {row["courtlistener_entry_id"] for row in rows}


def _row_to_docket_entry(row: sqlite3.Row) -> DocketEntry:
    return DocketEntry(
        courtlistener_entry_id=row["courtlistener_entry_id"],
        entry_number=row["entry_number"],
        description=row["description"] or "",
        date_filed=row["date_filed"],
    )


def list_seen_entries(db_path: str, tracked_docket_id: int) -> list[DocketEntry]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM seen_docket_entries
            WHERE tracked_docket_id = ?
            ORDER BY date_filed DESC, courtlistener_entry_id DESC
            """,
            (tracked_docket_id,),
        ).fetchall()
    return [_row_to_docket_entry(row) for row in rows]


def record_new_entries(db_path: str, tracked_docket_id: int, entries: list[DocketEntry]) -> None:
    first_seen_at = datetime.now().astimezone().isoformat()
    with _connect(db_path) as conn:
        conn.executemany(
            """
            INSERT OR IGNORE INTO seen_docket_entries
                (tracked_docket_id, courtlistener_entry_id, entry_number, description, date_filed, first_seen_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    tracked_docket_id,
                    entry.courtlistener_entry_id,
                    entry.entry_number,
                    entry.description,
                    entry.date_filed.isoformat() if entry.date_filed else None,
                    first_seen_at,
                )
                for entry in entries
            ],
        )


def update_last_checked(db_path: str, tracked_docket_id: int, checked_at: datetime) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE tracked_dockets SET last_checked_at = ? WHERE id = ?",
            (checked_at.isoformat(), tracked_docket_id),
        )


def create_alert(db_path: str, tracked_docket_id: int, new_entry_ids: list[int]) -> DocketAlert:
    created_at = datetime.now().astimezone().isoformat()
    with _connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO docket_alerts (tracked_docket_id, created_at, new_entry_count, new_entry_ids)
            VALUES (?, ?, ?, ?)
            """,
            (tracked_docket_id, created_at, len(new_entry_ids), json.dumps(new_entry_ids)),
        )
        row = conn.execute("SELECT * FROM docket_alerts WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _row_to_alert(row)


def list_alerts(db_path: str, tracked_docket_id: int) -> list[DocketAlert]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM docket_alerts WHERE tracked_docket_id = ? ORDER BY id", (tracked_docket_id,)
        ).fetchall()
    return [_row_to_alert(row) for row in rows]
