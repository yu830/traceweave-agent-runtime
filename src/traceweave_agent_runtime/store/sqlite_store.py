"""SQLite-backed session store."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from traceweave_agent_runtime.store.migrations import SCHEMA_SQL
from traceweave_agent_runtime.store.models import (
    MessageRecord,
    NoteRecord,
    SummaryRecord,
    TodoRecord,
    TraceRecord,
)
from traceweave_agent_runtime.utils.json_utils import to_json
from traceweave_agent_runtime.utils.time_utils import utc_now_iso
from traceweave_agent_runtime.utils.token_estimator import estimate_tokens


class SQLiteStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def upsert_session(
        self,
        user_id: str,
        session_id: str,
        title: str | None = None,
        max_context_tokens: int = 6000,
        max_recent_messages: int = 12,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (
                  user_id, session_id, title, status, max_context_tokens,
                  max_recent_messages, created_at, updated_at, metadata_json
                )
                VALUES (?, ?, ?, 'active', ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, session_id) DO UPDATE SET
                  title=COALESCE(excluded.title, sessions.title),
                  updated_at=excluded.updated_at,
                  max_context_tokens=excluded.max_context_tokens,
                  max_recent_messages=excluded.max_recent_messages
                """,
                (
                    user_id,
                    session_id,
                    title,
                    max_context_tokens,
                    max_recent_messages,
                    now,
                    now,
                    to_json(metadata or {}),
                ),
            )

    def add_message(
        self,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        content_type: str = "text",
        visibility: str = "default",
        metadata: dict[str, Any] | None = None,
    ) -> MessageRecord:
        now = utc_now_iso()
        token_estimate = estimate_tokens(content)
        with self._connect() as conn:
            turn_index = (
                conn.execute(
                    """
                    SELECT COALESCE(MAX(turn_index), 0) + 1
                    FROM messages
                    WHERE user_id=? AND session_id=?
                    """,
                    (user_id, session_id),
                ).fetchone()[0]
            )
            cursor = conn.execute(
                """
                INSERT INTO messages (
                  user_id, session_id, role, content, content_type, turn_index,
                  token_estimate, visibility, summarized, metadata_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    user_id,
                    session_id,
                    role,
                    content,
                    content_type,
                    turn_index,
                    token_estimate,
                    visibility,
                    to_json(metadata or {}),
                    now,
                ),
            )
            row = conn.execute(
                """
                SELECT id, user_id, session_id, role, content, turn_index,
                       token_estimate, summarized, created_at
                FROM messages
                WHERE user_id=? AND session_id=? AND id=?
                """,
                (user_id, session_id, cursor.lastrowid),
            ).fetchone()
        return self._message_from_row(row)

    def list_messages(
        self,
        user_id: str,
        session_id: str,
        limit: int | None = None,
        include_summarized: bool = True,
    ) -> list[MessageRecord]:
        query = """
            SELECT id, user_id, session_id, role, content, turn_index,
                   token_estimate, summarized, created_at
            FROM messages
            WHERE user_id=? AND session_id=?
        """
        params: list[Any] = [user_id, session_id]
        if not include_summarized:
            query += " AND summarized=0"
        query += " ORDER BY id ASC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._message_from_row(row) for row in rows]

    def list_recent_messages(
        self,
        user_id: str,
        session_id: str,
        limit: int,
        exclude_message_id: int | None = None,
    ) -> list[MessageRecord]:
        query = """
            SELECT id, user_id, session_id, role, content, turn_index,
                   token_estimate, summarized, created_at
            FROM messages
            WHERE user_id=? AND session_id=? AND summarized=0
        """
        params: list[Any] = [user_id, session_id]
        if exclude_message_id is not None:
            query += " AND id<>?"
            params.append(exclude_message_id)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._message_from_row(row) for row in reversed(rows)]

    def count_messages(self, user_id: str, session_id: str, include_summarized: bool = False) -> int:
        query = "SELECT COUNT(*) FROM messages WHERE user_id=? AND session_id=?"
        params: list[Any] = [user_id, session_id]
        if not include_summarized:
            query += " AND summarized=0"
        with self._connect() as conn:
            return int(conn.execute(query, params).fetchone()[0])

    def estimate_unsummarized_tokens(self, user_id: str, session_id: str) -> int:
        with self._connect() as conn:
            return int(
                conn.execute(
                    """
                    SELECT COALESCE(SUM(token_estimate), 0)
                    FROM messages
                    WHERE user_id=? AND session_id=? AND summarized=0
                    """,
                    (user_id, session_id),
                ).fetchone()[0]
            )

    def mark_messages_summarized(
        self,
        user_id: str,
        session_id: str,
        start_id: int,
        end_id: int,
        summary_id: int,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE messages
                SET summarized=1, summary_id=?
                WHERE user_id=? AND session_id=? AND id>=? AND id<=?
                """,
                (summary_id, user_id, session_id, start_id, end_id),
            )

    def add_summary(
        self,
        user_id: str,
        session_id: str,
        summary_text: str,
        start_message_id: int | None,
        end_message_id: int | None,
        compression_reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> SummaryRecord:
        now = utc_now_iso()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO summaries (
                  user_id, session_id, summary_text, start_message_id,
                  end_message_id, token_estimate, compression_reason,
                  created_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    session_id,
                    summary_text,
                    start_message_id,
                    end_message_id,
                    estimate_tokens(summary_text),
                    compression_reason,
                    now,
                    to_json(metadata or {}),
                ),
            )
            row = conn.execute(
                """
                SELECT id, user_id, session_id, summary_text, start_message_id,
                       end_message_id, token_estimate, compression_reason, created_at
                FROM summaries
                WHERE user_id=? AND session_id=? AND id=?
                """,
                (user_id, session_id, cursor.lastrowid),
            ).fetchone()
        return self._summary_from_row(row)

    def get_latest_summary(self, user_id: str, session_id: str) -> SummaryRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, user_id, session_id, summary_text, start_message_id,
                       end_message_id, token_estimate, compression_reason, created_at
                FROM summaries
                WHERE user_id=? AND session_id=?
                ORDER BY id DESC
                LIMIT 1
                """,
                (user_id, session_id),
            ).fetchone()
        return self._summary_from_row(row) if row else None

    def add_todo(self, user_id: str, session_id: str, title: str, status: str = "open") -> TodoRecord:
        now = utc_now_iso()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO todos (user_id, session_id, title, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, session_id, title, status, now, now),
            )
            row = conn.execute(
                """
                SELECT id, user_id, session_id, title, status, created_at, updated_at
                FROM todos
                WHERE user_id=? AND session_id=? AND id=?
                """,
                (user_id, session_id, cursor.lastrowid),
            ).fetchone()
        return self._todo_from_row(row)

    def list_todos(
        self,
        user_id: str,
        session_id: str,
        status: str | None = None,
    ) -> list[TodoRecord]:
        query = """
            SELECT id, user_id, session_id, title, status, created_at, updated_at
            FROM todos
            WHERE user_id=? AND session_id=?
        """
        params: list[Any] = [user_id, session_id]
        if status:
            query += " AND status=?"
            params.append(status)
        query += " ORDER BY id ASC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._todo_from_row(row) for row in rows]

    def update_todo(
        self,
        user_id: str,
        session_id: str,
        todo_id: int,
        title: str | None = None,
        status: str | None = None,
    ) -> TodoRecord | None:
        current = self.get_todo(user_id, session_id, todo_id)
        if current is None:
            return None
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE todos
                SET title=?, status=?, updated_at=?
                WHERE user_id=? AND session_id=? AND id=?
                """,
                (
                    title if title is not None else current.title,
                    status if status is not None else current.status,
                    now,
                    user_id,
                    session_id,
                    todo_id,
                ),
            )
        return self.get_todo(user_id, session_id, todo_id)

    def get_todo(self, user_id: str, session_id: str, todo_id: int) -> TodoRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, user_id, session_id, title, status, created_at, updated_at
                FROM todos
                WHERE user_id=? AND session_id=? AND id=?
                """,
                (user_id, session_id, todo_id),
            ).fetchone()
        return self._todo_from_row(row) if row else None

    def add_note(self, user_id: str, session_id: str, content: str) -> NoteRecord:
        now = utc_now_iso()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO notes (user_id, session_id, content, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, session_id, content, now),
            )
            row = conn.execute(
                """
                SELECT id, user_id, session_id, content, created_at
                FROM notes
                WHERE user_id=? AND session_id=? AND id=?
                """,
                (user_id, session_id, cursor.lastrowid),
            ).fetchone()
        return self._note_from_row(row)

    def list_notes(self, user_id: str, session_id: str) -> list[NoteRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, user_id, session_id, content, created_at
                FROM notes
                WHERE user_id=? AND session_id=?
                ORDER BY id ASC
                """,
                (user_id, session_id),
            ).fetchall()
        return [self._note_from_row(row) for row in rows]

    def add_trace(
        self,
        run_id: str,
        user_id: str,
        session_id: str,
        step_index: int,
        event_type: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
        result_summary: str = "",
        status: str = "success",
        error_type: str | None = None,
        error_message: str | None = None,
        latency_ms: int = 0,
    ) -> TraceRecord:
        now = utc_now_iso()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO tool_traces (
                  run_id, user_id, session_id, step_index, event_type, tool_name,
                  arguments_json, result_json, result_summary, status, error_type,
                  error_message, latency_ms, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    user_id,
                    session_id,
                    step_index,
                    event_type,
                    tool_name,
                    to_json(arguments or {}),
                    to_json(result or {}),
                    result_summary,
                    status,
                    error_type,
                    error_message,
                    latency_ms,
                    now,
                ),
            )
            row = conn.execute(
                """
                SELECT id, run_id, user_id, session_id, step_index, event_type,
                       tool_name, arguments_json, result_json, result_summary,
                       status, error_type, error_message, latency_ms, created_at
                FROM tool_traces
                WHERE user_id=? AND session_id=? AND id=?
                """,
                (user_id, session_id, cursor.lastrowid),
            ).fetchone()
        return self._trace_from_row(row)

    def list_traces(self, user_id: str, session_id: str) -> list[TraceRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, run_id, user_id, session_id, step_index, event_type,
                       tool_name, arguments_json, result_json, result_summary,
                       status, error_type, error_message, latency_ms, created_at
                FROM tool_traces
                WHERE user_id=? AND session_id=?
                ORDER BY id ASC
                """,
                (user_id, session_id),
            ).fetchall()
        return [self._trace_from_row(row) for row in rows]

    @staticmethod
    def _message_from_row(row: sqlite3.Row) -> MessageRecord:
        return MessageRecord(
            id=int(row["id"]),
            user_id=row["user_id"],
            session_id=row["session_id"],
            role=row["role"],
            content=row["content"],
            turn_index=int(row["turn_index"]),
            token_estimate=int(row["token_estimate"]),
            summarized=bool(row["summarized"]),
            created_at=row["created_at"],
        )

    @staticmethod
    def _todo_from_row(row: sqlite3.Row) -> TodoRecord:
        return TodoRecord(
            id=int(row["id"]),
            user_id=row["user_id"],
            session_id=row["session_id"],
            title=row["title"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _summary_from_row(row: sqlite3.Row) -> SummaryRecord:
        return SummaryRecord(
            id=int(row["id"]),
            user_id=row["user_id"],
            session_id=row["session_id"],
            summary_text=row["summary_text"],
            start_message_id=row["start_message_id"],
            end_message_id=row["end_message_id"],
            token_estimate=int(row["token_estimate"]),
            compression_reason=row["compression_reason"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _trace_from_row(row: sqlite3.Row) -> TraceRecord:
        return TraceRecord(
            id=int(row["id"]),
            run_id=row["run_id"],
            user_id=row["user_id"],
            session_id=row["session_id"],
            step_index=int(row["step_index"]),
            event_type=row["event_type"],
            tool_name=row["tool_name"],
            arguments_json=row["arguments_json"],
            result_json=row["result_json"],
            result_summary=row["result_summary"],
            status=row["status"],
            error_type=row["error_type"],
            error_message=row["error_message"],
            latency_ms=int(row["latency_ms"]),
            created_at=row["created_at"],
        )

    @staticmethod
    def _note_from_row(row: sqlite3.Row) -> NoteRecord:
        return NoteRecord(
            id=int(row["id"]),
            user_id=row["user_id"],
            session_id=row["session_id"],
            content=row["content"],
            created_at=row["created_at"],
        )

