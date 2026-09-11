import sqlite3
from datetime import datetime

from legalintel.auth import db as auth_db
from legalintel.auth.db import UserRecord
from legalintel.models.organization import Organization
from legalintel.storage import connect as _connect


def _row_to_organization(row: sqlite3.Row) -> Organization:
    return Organization(
        id=row["id"],
        name=row["name"],
        plan=row["plan"],
        subscription_status=row["subscription_status"],
        stripe_customer_id=row["stripe_customer_id"],
        stripe_subscription_id=row["stripe_subscription_id"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def create_organization_with_owner(
    db_path: str, *, organization_name: str, email: str, name: str, password_hash: str
) -> tuple[Organization, UserRecord]:
    """The one multi-table transactional write in this app outside
    `matters.db.delete_matter`'s cascade - inserts `organizations` then `users` in a
    single connect() block so a crash mid-way never leaves an org with no owner.
    The new user is always role="attorney", is_platform_admin=False - this is how
    a brand-new customer organization gets its first (and, at signup time, only)
    member. Raises sqlite3.IntegrityError on a duplicate email; callers (the
    /auth/register route) should pre-check via auth_db.get_user_by_email for the
    friendlier 409 response, same convention as POST /auth/users."""
    created_at = datetime.now().astimezone().isoformat()
    with _connect(db_path) as conn:
        org_cursor = conn.execute(
            "INSERT INTO organizations (name, plan, subscription_status, created_at) VALUES (?, 'free', 'active', ?)",
            (organization_name, created_at),
        )
        organization_id = org_cursor.lastrowid

        user_cursor = conn.execute(
            """
            INSERT INTO users (email, name, password_hash, role, organization_id, is_platform_admin, created_at)
            VALUES (?, ?, ?, 'attorney', ?, 0, ?)
            """,
            (email, name, password_hash, organization_id, created_at),
        )
        user_id = user_cursor.lastrowid
        org_row = conn.execute("SELECT * FROM organizations WHERE id = ?", (organization_id,)).fetchone()

    organization = _row_to_organization(org_row)
    user = auth_db.get_user_by_id(db_path, user_id)
    assert user is not None  # just inserted, in the same call
    return organization, user


def create_organization(db_path: str, *, name: str) -> Organization:
    """Creates a standalone organization with no owner yet - used by tests and by
    future platform-admin tooling. The public registration flow uses
    create_organization_with_owner instead, so an org is never left ownerless."""
    created_at = datetime.now().astimezone().isoformat()
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO organizations (name, plan, subscription_status, created_at) VALUES (?, 'free', 'active', ?)",
            (name, created_at),
        )
        row = conn.execute("SELECT * FROM organizations WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _row_to_organization(row)


def get_organization(db_path: str, organization_id: int) -> Organization | None:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM organizations WHERE id = ?", (organization_id,)).fetchone()
    return _row_to_organization(row) if row is not None else None


def get_organization_by_stripe_customer_id(db_path: str, stripe_customer_id: str) -> Organization | None:
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM organizations WHERE stripe_customer_id = ?", (stripe_customer_id,)
        ).fetchone()
    return _row_to_organization(row) if row is not None else None


def get_organization_by_stripe_subscription_id(db_path: str, stripe_subscription_id: str) -> Organization | None:
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM organizations WHERE stripe_subscription_id = ?", (stripe_subscription_id,)
        ).fetchone()
    return _row_to_organization(row) if row is not None else None


_UPDATABLE_ORGANIZATION_FIELDS = {"plan", "subscription_status", "stripe_customer_id", "stripe_subscription_id"}


def update_organization(db_path: str, organization_id: int, **fields) -> Organization | None:
    """Used by the Stripe webhook handlers (legalintel.billing.webhook_handlers) to
    sync plan/subscription state - not exposed as a general-purpose setter, so the
    allow-list below is deliberately narrow."""
    if not fields:
        return get_organization(db_path, organization_id)
    unknown = set(fields) - _UPDATABLE_ORGANIZATION_FIELDS
    if unknown:
        raise ValueError(f"Cannot update organization field(s): {sorted(unknown)}")

    set_clause = ", ".join(f"{key} = ?" for key in fields)
    with _connect(db_path) as conn:
        conn.execute(
            f"UPDATE organizations SET {set_clause} WHERE id = ?",  # noqa: S608 - keys from a fixed allow-list above
            (*fields.values(), organization_id),
        )
        row = conn.execute("SELECT * FROM organizations WHERE id = ?", (organization_id,)).fetchone()
    return _row_to_organization(row) if row is not None else None
