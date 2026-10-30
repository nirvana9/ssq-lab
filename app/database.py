from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = Path(os.environ.get("SSQ_DB_PATH", DATA_DIR / "ssq_lab.db"))


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db() -> Iterable[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS draws (
                issue TEXT PRIMARY KEY,
                draw_date TEXT NOT NULL,
                red_json TEXT NOT NULL,
                blue INTEGER NOT NULL,
                sales TEXT,
                poolmoney TEXT,
                prizegrades_json TEXT,
                source TEXT NOT NULL DEFAULT 'cwl.gov.cn',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_draws_date ON draws(draw_date);
            CREATE TABLE IF NOT EXISTS app_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )


def upsert_draws(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    with db() as conn:
        before = conn.total_changes
        conn.executemany(
            """INSERT INTO draws(issue, draw_date, red_json, blue, sales, poolmoney,
                                  prizegrades_json, source, updated_at)
               VALUES(:issue, :draw_date, :red_json, :blue, :sales, :poolmoney,
                      :prizegrades_json, :source, CURRENT_TIMESTAMP)
               ON CONFLICT(issue) DO UPDATE SET
                 draw_date=excluded.draw_date,
                 red_json=excluded.red_json,
                 blue=excluded.blue,
                 sales=excluded.sales,
                 poolmoney=excluded.poolmoney,
                 prizegrades_json=excluded.prizegrades_json,
                 source=excluded.source,
                 updated_at=CURRENT_TIMESTAMP
            """,
            [
                {
                    **r,
                    "red_json": json.dumps(r["red"], ensure_ascii=False),
                    "prizegrades_json": json.dumps(r.get("prizegrades") or [], ensure_ascii=False),
                    "source": r.get("source", "cwl.gov.cn"),
                }
                for r in rows
            ],
        )
        return conn.total_changes - before


def list_draws(limit: int | None = None, newest_first: bool = False) -> list[dict[str, Any]]:
    order = "DESC" if newest_first else "ASC"
    sql = f"SELECT * FROM draws ORDER BY issue {order}"
    params: tuple[Any, ...] = ()
    if limit is not None:
        sql += " LIMIT ?"
        params = (limit,)
    with db() as conn:
        records = conn.execute(sql, params).fetchall()
    result: list[dict[str, Any]] = []
    for row in records:
        item = dict(row)
        item["red"] = json.loads(item.pop("red_json"))
        item["prizegrades"] = json.loads(item.pop("prizegrades_json") or "[]")
        result.append(item)
    return result


def get_meta(key: str, default: str | None = None) -> str | None:
    with db() as conn:
        row = conn.execute("SELECT value FROM app_meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_meta(key: str, value: str) -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO app_meta(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def count_draws() -> int:
    with db() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM draws").fetchone()[0])


def latest_draw() -> dict[str, Any] | None:
    rows = list_draws(limit=1, newest_first=True)
    return rows[0] if rows else None


def import_draws(rows: list[dict[str, Any]], replace: bool = False) -> int:
    if replace:
        with db() as conn:
            conn.execute("DELETE FROM draws")
    return upsert_draws(rows)
