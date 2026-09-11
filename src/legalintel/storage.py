import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    plan TEXT NOT NULL DEFAULT 'free' CHECK (plan IN ('free', 'pro')),
    subscription_status TEXT NOT NULL DEFAULT 'active'
        CHECK (subscription_status IN ('active', 'past_due', 'canceled')),
    stripe_customer_id TEXT UNIQUE,
    stripe_subscription_id TEXT UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('attorney', 'paralegal', 'support_staff')),
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS matters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    created_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS matter_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    matter_id INTEGER NOT NULL REFERENCES matters(id),
    source_filename TEXT NOT NULL,
    analysis_type TEXT NOT NULL CHECK (analysis_type IN ('parse', 'extract_clauses', 'classify')),
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tracked_dockets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    courtlistener_docket_id INTEGER NOT NULL UNIQUE,
    court TEXT,
    docket_number TEXT,
    case_name TEXT,
    matter_id INTEGER REFERENCES matters(id),
    created_at TEXT NOT NULL,
    last_checked_at TEXT
);

CREATE TABLE IF NOT EXISTS seen_docket_entries (
    tracked_docket_id INTEGER NOT NULL REFERENCES tracked_dockets(id),
    courtlistener_entry_id INTEGER NOT NULL,
    entry_number INTEGER,
    description TEXT,
    date_filed TEXT,
    first_seen_at TEXT NOT NULL,
    PRIMARY KEY (tracked_docket_id, courtlistener_entry_id)
);

CREATE TABLE IF NOT EXISTS docket_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tracked_docket_id INTEGER NOT NULL REFERENCES tracked_dockets(id),
    created_at TEXT NOT NULL,
    new_entry_count INTEGER NOT NULL,
    new_entry_ids TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    action TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS clause_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    matter_document_id INTEGER NOT NULL REFERENCES matter_documents(id),
    clause_index INTEGER NOT NULL,
    reviewed_by INTEGER NOT NULL REFERENCES users(id),
    reviewed_at TEXT NOT NULL,
    UNIQUE (matter_document_id, clause_index)
);
"""


# SQLite's ALTER TABLE can't add a NOT NULL/CHECK-constrained column to a non-empty
# table without a full table rebuild (a migration tool this repo has never needed and
# isn't introducing now) - so these land as nullable at the schema level even though
# every *new* row is required to set them. That requirement is enforced in the
# `*_db.py` write functions (organization_id is a required keyword arg there), not
# by the schema. `ADD COLUMN` is metadata-only in SQLite, so re-running this on every
# connect() is cheap, matching the "just re-run CREATE TABLE IF NOT EXISTS" philosophy
# already used above.
_ADD_COLUMN_MIGRATIONS = [
    ("users", "organization_id", "INTEGER REFERENCES organizations(id)"),
    ("users", "is_platform_admin", "INTEGER NOT NULL DEFAULT 0"),
    ("matters", "organization_id", "INTEGER"),
    ("tracked_dockets", "organization_id", "INTEGER"),
    ("audit_log", "organization_id", "INTEGER REFERENCES organizations(id)"),
]


def _apply_add_column_migrations(conn: sqlite3.Connection) -> None:
    for table, column, decl in _ADD_COLUMN_MIGRATIONS:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
        except sqlite3.OperationalError as exc:
            if "duplicate column name" not in str(exc):
                raise


def _backfill_legacy_organization(conn: sqlite3.Connection) -> None:
    """One-time migration for a database that was single-tenant before organizations
    existed (e.g. the already-deployed production DB): groups every pre-existing
    user/matter/tracked-docket into one new "Legacy Organization" row. This is the
    correct migration, not a hack - that data already had zero isolation from each
    other (every user saw every matter), so putting them all in one org together
    changes nothing about who could see what."""
    orphans = conn.execute(
        "SELECT COUNT(*) FROM users WHERE organization_id IS NULL AND is_platform_admin = 0"
    ).fetchone()[0]
    if orphans == 0:
        return

    created_at = datetime.now().astimezone().isoformat()
    cursor = conn.execute(
        "INSERT INTO organizations (name, plan, subscription_status, created_at) VALUES (?, 'free', 'active', ?)",
        ("Legacy Organization", created_at),
    )
    organization_id = cursor.lastrowid
    conn.execute(
        "UPDATE users SET organization_id = ? WHERE organization_id IS NULL AND is_platform_admin = 0",
        (organization_id,),
    )
    conn.execute("UPDATE matters SET organization_id = ? WHERE organization_id IS NULL", (organization_id,))
    conn.execute(
        "UPDATE tracked_dockets SET organization_id = ? WHERE organization_id IS NULL", (organization_id,)
    )


@contextmanager
def connect(db_path: str) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(_CREATE_TABLES)
        _apply_add_column_migrations(conn)
        _backfill_legacy_organization(conn)
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str) -> None:
    with connect(db_path):
        pass
