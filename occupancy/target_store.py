"""
SQLite-backed store for per-property target occupancy percentages.

Schema: property_id TEXT PRIMARY KEY, target_rate REAL, updated_at TEXT
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class TargetStore:
    def __init__(self, db_path: str) -> None:
        self._path = db_path
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS property_targets (
                    property_id TEXT PRIMARY KEY,
                    target_rate  REAL NOT NULL,
                    updated_at   TEXT NOT NULL
                )
            """)

    def get(self, property_id: str) -> Optional[float]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT target_rate FROM property_targets WHERE property_id = ?",
                (property_id,)
            ).fetchone()
            return float(row["target_rate"]) if row else None

    def get_all(self) -> dict[str, float]:
        with self._conn() as conn:
            rows = conn.execute("SELECT property_id, target_rate FROM property_targets").fetchall()
            return {r["property_id"]: float(r["target_rate"]) for r in rows}

    def set(self, property_id: str, target_rate: float) -> None:
        if not 0.0 <= target_rate <= 1.0:
            raise ValueError(f"target_rate must be 0.0–1.0, got {target_rate}")
        now = datetime.now(tz=timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO property_targets (property_id, target_rate, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(property_id) DO UPDATE SET
                    target_rate = excluded.target_rate,
                    updated_at  = excluded.updated_at
            """, (property_id, target_rate, now))

    def set_bulk(self, targets: dict[str, float]) -> None:
        now = datetime.now(tz=timezone.utc).isoformat()
        with self._conn() as conn:
            for pid, rate in targets.items():
                if not 0.0 <= rate <= 1.0:
                    raise ValueError(f"target_rate for {pid} must be 0.0–1.0, got {rate}")
                conn.execute("""
                    INSERT INTO property_targets (property_id, target_rate, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(property_id) DO UPDATE SET
                        target_rate = excluded.target_rate,
                        updated_at  = excluded.updated_at
                """, (pid, rate, now))
