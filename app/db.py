import os
import sqlite3
from pathlib import Path


def db_path() -> Path:
    raw = os.environ.get("DB_PATH", "data/vyruchka.db")
    return Path(raw)


def connect() -> sqlite3.Connection:
    p = db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL DEFAULT 'user',
    full_name     TEXT    NOT NULL DEFAULT '',
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS rows (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    fio        TEXT    NOT NULL,
    tab_num    TEXT    NOT NULL DEFAULT '',
    date       TEXT    NOT NULL DEFAULT '',
    route      TEXT    NOT NULL DEFAULT '',
    cash       REAL    NOT NULL DEFAULT 0,
    card       REAL    NOT NULL DEFAULT 0,
    card_av    REAL    NOT NULL DEFAULT 0,
    created_by TEXT    NOT NULL DEFAULT '',
    created_at TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_rows_date ON rows(date);
CREATE INDEX IF NOT EXISTS idx_rows_fio  ON rows(fio);

CREATE TABLE IF NOT EXISTS drivers (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    fio     TEXT NOT NULL UNIQUE,
    tab_num TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS routes (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    username   TEXT NOT NULL DEFAULT '',
    action     TEXT NOT NULL,
    detail     TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);
"""


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def query_all(sql: str, params: tuple = ()) -> list[dict]:
    with connect() as conn:
        cur = conn.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def query_one(sql: str, params: tuple = ()) -> dict | None:
    with connect() as conn:
        cur = conn.execute(sql, params)
        r = cur.fetchone()
        return dict(r) if r else None


def execute(sql: str, params: tuple = ()) -> int:
    with connect() as conn:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid