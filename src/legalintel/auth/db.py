import sqlite3
from datetime import datetime

from pydantic import BaseModel

from legalintel.models.user import AuditLogEntry, Role
from legalintel.storage import connect as _connect


class UserRecord(BaseModel):
    """Internal representation, includes the password hash. Never return this
    directly from a route - convert to the public `User` model first (drops
    `password_hash`)."""

    id: int
    email: str
    name: str
    password_hash: str
    role: Role
    is_active: bool
    organization_id: int | None
    is_platform_admin: bool
    created_at: datetime


class ClauseReviewRecord(BaseModel):
    """Internal representation - no reviewer display name (that requires a join
    against `users`, done by the caller via `get_user_by_id`, not here)."""

    matter_document_id: int
    clause_index: int
    reviewed_by: int
    reviewed_at: datetime


def _row_to_user_record(row: sqlite3.Row) -> UserRecord:
    return UserRecord(
        id=row["id"],
        email=row["email"],
        name=row["name"],
        password_hash=row["password_hash"],
        role=row["role"],
        is_active=bool(row["is_active"]),
        organization_id=row["organization_id"],
        is_platform_admin=bool(row["is_platform_admin"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def create_user(
    db_path: str,
    *,
    email: str,
    name: str,
    password_hash: str,
    role: Role,
    organization_id: int | None = None,
    is_platform_admin: bool = False,
) -> UserRecord:
    """`organization_id=None` is only valid for `is_platform_admin=True` accounts
    (bootstrapped via a CLI script, not through this function's typical caller
    `POST /auth/users`, which always forces the caller's own organization_id).
    Registering a brand-new organization's first user goes through
    `legalintel.organizations.db.create_organization_with_owner` instead, so the
    org and its owner are created in one transaction - not through here."""
    created_at = datetime.now().astimezone().isoformat()
    with _connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO users (email, name, password_hash, role, organization_id, is_platform_admin, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (email, name, password_hash, role, organization_id, int(is_platform_admin), created_at),
        )
        row = conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _row_to_user_record(row)


def get_user_by_email(db_path: str, email: str) -> UserRecord | None:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    return _row_to_user_record(row) if row is not None else None


def get_user_by_id(db_path: str, user_id: int) -> UserRecord | None:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _row_to_user_record(row) if row is not None else None


def list_users(db_path: str) -> list[UserRecord]:
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
    return [_row_to_user_record(row) for row in rows]


def _row_to_audit_log_entry(row: sqlite3.Row) -> AuditLogEntry:
    return AuditLogEntry(
        id=row["id"],
        user_id=row["user_id"],
        action=row["action"],
        detail=row["detail"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def log_action(
    db_path: str, *, user_id: int | None, action: str, detail: str | None = None, organization_id: int | None = None
) -> AuditLogEntry:
    """organization_id is None for platform-admin actions that aren't about any one
    org (e.g. a future platform-wide event) - every org-scoped action (login, matter
    creation, clause review, etc.) should pass the acting user's organization_id so
    `list_audit_log` can filter to just that org."""
    created_at = datetime.now().astimezone().isoformat()
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO audit_log (user_id, action, detail, organization_id, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, action, detail, organization_id, created_at),
        )
        row = conn.execute("SELECT * FROM audit_log WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _row_to_audit_log_entry(row)


def list_audit_log(db_path: str, organization_id: int) -> list[AuditLogEntry]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log WHERE organization_id = ? ORDER BY id DESC", (organization_id,)
        ).fetchall()
    return [_row_to_audit_log_entry(row) for row in rows]


def _row_to_clause_review_record(row: sqlite3.Row) -> ClauseReviewRecord:
    return ClauseReviewRecord(
        matter_document_id=row["matter_document_id"],
        clause_index=row["clause_index"],
        reviewed_by=row["reviewed_by"],
        reviewed_at=datetime.fromisoformat(row["reviewed_at"]),
    )


def set_clause_reviewed(
    db_path: str, *, matter_document_id: int, clause_index: int, reviewed_by: int
) -> ClauseReviewRecord:
    reviewed_at = datetime.now().astimezone().isoformat()
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO clause_reviews (matter_document_id, clause_index, reviewed_by, reviewed_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (matter_document_id, clause_index)
            DO UPDATE SET reviewed_by = excluded.reviewed_by, reviewed_at = excluded.reviewed_at
            """,
            (matter_document_id, clause_index, reviewed_by, reviewed_at),
        )
        row = conn.execute(
            "SELECT * FROM clause_reviews WHERE matter_document_id = ? AND clause_index = ?",
            (matter_document_id, clause_index),
        ).fetchone()
    return _row_to_clause_review_record(row)


def unset_clause_reviewed(db_path: str, *, matter_document_id: int, clause_index: int) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            "DELETE FROM clause_reviews WHERE matter_document_id = ? AND clause_index = ?",
            (matter_document_id, clause_index),
        )


def list_clause_reviews(db_path: str, matter_document_id: int) -> list[ClauseReviewRecord]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM clause_reviews WHERE matter_document_id = ? ORDER BY clause_index",
            (matter_document_id,),
        ).fetchall()
    return [_row_to_clause_review_record(row) for row in rows]
