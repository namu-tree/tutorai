from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

from core.models import SessionState, SessionUpdate, StudentEvent, TaskSpec


@dataclass(frozen=True)
class EventStoreConfig:
    sqlite_path: str

    @staticmethod
    def from_env() -> "EventStoreConfig":
        path = os.getenv("EVENT_STORE_SQLITE_PATH", os.path.join(os.getcwd(), "tutorai_events.sqlite3"))
        return EventStoreConfig(sqlite_path=path)


class SQLiteEventStore:
    def __init__(self, config: Optional[EventStoreConfig] = None) -> None:
        self.config = config or EventStoreConfig.from_env()
        self._init_db()

    @contextmanager
    def _conn(self) -> Iterable[sqlite3.Connection]:
        conn = sqlite3.connect(self.config.sqlite_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                  session_id TEXT PRIMARY KEY,
                  task_spec_json TEXT,
                  created_at TEXT,
                  updated_at TEXT,
                  last_message TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS student_events (
                  event_id TEXT PRIMARY KEY,
                  session_id TEXT,
                  event_type TEXT,
                  created_at TEXT,
                  payload_json TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_student_events_session_time
                ON student_events(session_id, created_at)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS session_updates (
                  update_id TEXT PRIMARY KEY,
                  session_id TEXT,
                  update_type TEXT,
                  created_at TEXT,
                  data_json TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_session_updates_session_time
                ON session_updates(session_id, created_at)
                """
            )

    def upsert_session(self, state: SessionState) -> None:
        task_spec_json = state.task_spec.model_dump_json() if state.task_spec else None
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO sessions(session_id, task_spec_json, created_at, updated_at, last_message)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                  task_spec_json=excluded.task_spec_json,
                  updated_at=excluded.updated_at,
                  last_message=excluded.last_message
                """,
                (
                    state.session_id,
                    task_spec_json,
                    state.created_at,
                    state.updated_at,
                    state.last_message,
                ),
            )

    def get_session(self, session_id: str) -> Optional[SessionState]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT session_id, task_spec_json, created_at, updated_at, last_message FROM sessions WHERE session_id=?",
                (session_id,),
            ).fetchone()
            if not row:
                return None
            task_spec = None
            if row["task_spec_json"]:
                task_spec = TaskSpec.model_validate_json(row["task_spec_json"])
            return SessionState(
                session_id=row["session_id"],
                task_spec=task_spec,
                last_message=row["last_message"] or "",
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    def append_student_event(self, event: StudentEvent) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO student_events(event_id, session_id, event_type, created_at, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.session_id,
                    event.event_type.value,
                    event.created_at,
                    json.dumps(event.payload, ensure_ascii=False),
                ),
            )

    def append_session_update(self, update: SessionUpdate) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO session_updates(update_id, session_id, update_type, created_at, data_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    update.update_id,
                    update.session_id,
                    update.update_type.value,
                    update.created_at,
                    json.dumps(update.data, ensure_ascii=False),
                ),
            )

    def list_updates(self, session_id: str, limit: int = 100) -> list[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT update_id, update_type, created_at, data_json
                FROM session_updates
                WHERE session_id=?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
            result: list[Dict[str, Any]] = []
            for r in rows:
                result.append(
                    {
                        "update_id": r["update_id"],
                        "update_type": r["update_type"],
                        "created_at": r["created_at"],
                        "data": json.loads(r["data_json"] or "{}"),
                    }
                )
            return result

