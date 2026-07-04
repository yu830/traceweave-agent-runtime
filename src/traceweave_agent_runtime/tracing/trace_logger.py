"""Trace logging facade over SQLiteStore."""

from __future__ import annotations

from typing import Any

from traceweave_agent_runtime.store.sqlite_store import SQLiteStore


class TraceLogger:
    def __init__(self, store: SQLiteStore):
        self.store = store

    def log_event(
        self,
        run_id: str,
        user_id: str,
        session_id: str,
        step_index: int,
        event_type: str,
        tool_name: str = "__runtime__",
        arguments: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
        result_summary: str = "",
        status: str = "success",
        error_type: str | None = None,
        error_message: str | None = None,
        latency_ms: int = 0,
    ) -> None:
        self.store.add_trace(
            run_id=run_id,
            user_id=user_id,
            session_id=session_id,
            step_index=step_index,
            event_type=event_type,
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            result_summary=result_summary,
            status=status,
            error_type=error_type,
            error_message=error_message,
            latency_ms=latency_ms,
        )

    def llm_request(
        self,
        run_id: str,
        user_id: str,
        session_id: str,
        step_index: int,
        messages: list[dict[str, str]],
    ) -> None:
        self.log_event(
            run_id,
            user_id,
            session_id,
            step_index,
            "llm_request",
            "__llm__",
            arguments={"message_count": len(messages)},
            result={"messages": messages},
            result_summary=f"LLM request with {len(messages)} context messages",
        )

    def llm_response(
        self,
        run_id: str,
        user_id: str,
        session_id: str,
        step_index: int,
        raw_response: str,
        latency_ms: int,
    ) -> None:
        self.log_event(
            run_id,
            user_id,
            session_id,
            step_index,
            "llm_response",
            "__llm__",
            result={"raw_response": raw_response},
            result_summary=raw_response[:500],
            latency_ms=latency_ms,
        )

    def parser_error(
        self,
        run_id: str,
        user_id: str,
        session_id: str,
        step_index: int,
        error: Exception,
        raw_response: str,
    ) -> None:
        self.log_event(
            run_id,
            user_id,
            session_id,
            step_index,
            "parser_error",
            "__parser__",
            result={"raw_response": raw_response},
            result_summary="Parser failed to parse or validate LLM response",
            status="error",
            error_type=type(error).__name__,
            error_message=str(error),
        )

