"""Typed records returned by the SQLite store."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MessageRecord:
    id: int
    user_id: str
    session_id: str
    role: str
    content: str
    turn_index: int
    token_estimate: int
    summarized: bool
    created_at: str


@dataclass(frozen=True)
class TodoRecord:
    id: int
    user_id: str
    session_id: str
    title: str
    status: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class SummaryRecord:
    id: int
    user_id: str
    session_id: str
    summary_text: str
    start_message_id: int | None
    end_message_id: int | None
    token_estimate: int
    compression_reason: str
    created_at: str


@dataclass(frozen=True)
class TraceRecord:
    id: int
    run_id: str
    user_id: str
    session_id: str
    step_index: int
    event_type: str
    tool_name: str
    arguments_json: str
    result_json: str
    result_summary: str
    status: str
    error_type: str | None
    error_message: str | None
    latency_ms: int
    created_at: str


@dataclass(frozen=True)
class NoteRecord:
    id: int
    user_id: str
    session_id: str
    content: str
    created_at: str

