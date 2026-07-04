"""Deterministic context compression."""

from __future__ import annotations

from traceweave_agent_runtime.store.models import SummaryRecord
from traceweave_agent_runtime.store.sqlite_store import SQLiteStore
from traceweave_agent_runtime.tracing.trace_logger import TraceLogger
from traceweave_agent_runtime.utils.token_estimator import estimate_tokens


class DeterministicCompressor:
    def __init__(
        self,
        store: SQLiteStore,
        max_recent_messages: int = 12,
        max_context_tokens: int = 6000,
        summary_target_tokens: int = 800,
    ) -> None:
        self.store = store
        self.max_recent_messages = max_recent_messages
        self.max_context_tokens = max_context_tokens
        self.summary_target_tokens = summary_target_tokens

    def should_compress(self, user_id: str, session_id: str) -> tuple[bool, str]:
        count = self.store.count_messages(user_id, session_id, include_summarized=False)
        if count > self.max_recent_messages:
            return True, f"messages_count>{self.max_recent_messages}"
        estimated = self.store.estimate_unsummarized_tokens(user_id, session_id)
        if estimated > self.max_context_tokens:
            return True, f"estimated_context_tokens>{self.max_context_tokens}"
        return False, "not_needed"

    def compress_if_needed(
        self,
        user_id: str,
        session_id: str,
        run_id: str | None = None,
        trace_logger: TraceLogger | None = None,
    ) -> SummaryRecord | None:
        should_compress, reason = self.should_compress(user_id, session_id)
        if not should_compress:
            return None
        messages = self.store.list_messages(user_id, session_id, include_summarized=False)
        old_messages = messages[: -self.max_recent_messages]
        if not old_messages:
            return None
        summary_text = self._build_summary(user_id, session_id, old_messages)
        start_id = old_messages[0].id
        end_id = old_messages[-1].id
        summary = self.store.add_summary(
            user_id,
            session_id,
            summary_text=summary_text,
            start_message_id=start_id,
            end_message_id=end_id,
            compression_reason=reason,
        )
        self.store.mark_messages_summarized(user_id, session_id, start_id, end_id, summary.id)
        if trace_logger is not None and run_id is not None:
            trace_logger.log_event(
                run_id=run_id,
                user_id=user_id,
                session_id=session_id,
                step_index=0,
                event_type="compression",
                tool_name="__compression__",
                arguments={"reason": reason, "start_message_id": start_id, "end_message_id": end_id},
                result={"summary_id": summary.id, "token_estimate": summary.token_estimate},
                result_summary=f"Compressed messages {start_id}-{end_id}.",
            )
        return summary

    def _build_summary(self, user_id: str, session_id: str, messages) -> str:
        open_todos = self.store.list_todos(user_id, session_id, status="open")
        snippets = "\n".join(
            f"- {message.role}#{message.id}: {message.content[:180]}" for message in messages
        )
        todo_block = "\n".join(f"- #{todo.id}: {todo.title}" for todo in open_todos) or "- None"
        summary = f"""User goals:
- Preserve the intent and outcomes from older turns in this session.

Completed work:
- See compressed message snippets for completed conversational steps.

Unfinished work:
{todo_block}

Important facts:
{snippets}

Tool key results:
- Full tool results are kept in trace logs; only relevant summaries should enter future context.

User preferences:
- Keep answers concise and operational unless the user asks for more detail.

Unresolved questions:
- None detected by deterministic compressor.
"""
        max_chars = max(400, self.summary_target_tokens * 4)
        if estimate_tokens(summary) > self.summary_target_tokens:
            summary = summary[:max_chars]
        return summary

