"""SQLite database utilities for persistent user, profile, policy, trigger, and claim data."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Lock

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "covrly.sqlite3"
DB_LOCK = Lock()


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS registration_otps (
    email TEXT PRIMARY KEY,
    otp_hash TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profiles (
    user_id TEXT PRIMARY KEY,
    name TEXT,
    phone TEXT,
    city TEXT,
    vehicle_type TEXT,
    profile_image_url TEXT NOT NULL DEFAULT '',
    is_complete INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS policies (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    policy_type TEXT NOT NULL,
    base_premium REAL NOT NULL,
    dynamic_premium REAL NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_policies_user_id ON policies(user_id);
CREATE INDEX IF NOT EXISTS idx_policies_user_type ON policies(user_id, policy_type);

CREATE TABLE IF NOT EXISTS triggers (
    trigger_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    trigger_type TEXT NOT NULL,
    fraud_score REAL NOT NULL,
    location_lat REAL NOT NULL,
    location_lng REAL NOT NULL,
    timestamp TEXT NOT NULL,
    policy_types_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS location_snapshots (
    user_id TEXT PRIMARY KEY,
    location_lat REAL NOT NULL,
    location_lng REAL NOT NULL,
    timestamp TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    claim_type TEXT NOT NULL,
    status TEXT NOT NULL,
    payout REAL NOT NULL,
    payout_candidate REAL NOT NULL,
    timestamp TEXT NOT NULL,
    reason TEXT NOT NULL,
    trigger_type TEXT NOT NULL,
    fraud_score REAL NOT NULL,
    verification_required INTEGER NOT NULL,
    policy_type TEXT NOT NULL,
    user_location_lat REAL NOT NULL,
    user_location_lng REAL NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_claims_user_id ON claims(user_id);
CREATE INDEX IF NOT EXISTS idx_claims_status ON claims(status);
CREATE INDEX IF NOT EXISTS idx_location_snapshots_updated_at ON location_snapshots(updated_at);
CREATE INDEX IF NOT EXISTS idx_registration_otps_expires_at ON registration_otps(expires_at);
"""


def _ensure_db_dir() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    _ensure_db_dir()
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _table_has_column(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(str(row[1]) == column_name for row in rows)


def _run_migrations(conn: sqlite3.Connection) -> None:
    if not _table_has_column(conn, "triggers", "user_id"):
        conn.execute("ALTER TABLE triggers ADD COLUMN user_id TEXT NOT NULL DEFAULT 'system'")

    if not _table_has_column(conn, "profiles", "profile_image_url"):
        conn.execute("ALTER TABLE profiles ADD COLUMN profile_image_url TEXT NOT NULL DEFAULT ''")


def init_sqlite_db() -> None:
    _ensure_db_dir()
    with DB_LOCK:
        with get_connection() as conn:
            conn.executescript(SCHEMA_SQL)
            _run_migrations(conn)
            conn.commit()
