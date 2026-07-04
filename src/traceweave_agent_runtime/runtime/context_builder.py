"""Context construction for each LLM call."""

from __future__ import annotations

from traceweave_agent_runtime.store.sqlite_store import SQLiteStore
from traceweave_agent_runtime.tools.registry import ToolRegistry
from traceweave_agent_runtime.utils.json_utils import to_pretty_json


SYSTEM_PROMPT = """You are TraceWeave, a minimal tool-using agent runtime.
You must respond with exactly one JSON object matching the JSON Action Protocol.
Do not use native function calling. Do not include full chain-of-thought.
Use reasoning_summary only for a short operational summary."""

RUNTIME_POLICY = """JSON Action Protocol:
{
  "action": "tool_call" | "final_answer",
  "reasoning_summary": "short summary only",
  "tool_call": {"name": "tool_name", "arguments": {}} | null,
  "final_answer": "..." | null
}
If calling a tool, final_answer must be null. If answering, tool_call must be null."""


class ContextBuilder:
    def __init__(
        self,
        store: SQLiteStore,
        tool_registry: ToolRegistry,
        max_recent_messages: int = 12,
    ) -> None:
        self.store = store
        self.tool_registry = tool_registry
        self.max_recent_messages = max_recent_messages

    def build(
        self,
        user_id: str,
        session_id: str,
        current_user_message: str,
        current_message_id: int | None = None,
        latest_tool_result_summary: str | None = None,
    ) -> list[dict[str, str]]:
        summary = self.store.get_latest_summary(user_id, session_id)
        open_todos = self.store.list_todos(user_id, session_id, status="open")
        recent_messages = self.store.list_recent_messages(
            user_id,
            session_id,
            limit=self.max_recent_messages,
            exclude_message_id=current_message_id,
        )
        messages: list[dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": f"Runtime Policy:\n{RUNTIME_POLICY}"},
            {
                "role": "system",
                "content": "Tool Schema Block:\n" + to_pretty_json(self.tool_registry.list_schemas_for_llm()),
            },
            {
                "role": "system",
                "content": "Relevant Memory Block:\nNo global memory store is enabled in this minimal runtime.",
            },
            {
                "role": "system",
                "content": "Session Summary Block:\n"
                + (summary.summary_text if summary else "No compressed session summary yet."),
            },
            {
                "role": "system",
                "content": "Open Todos Block:\n"
                + (
                    "\n".join(f"- #{todo.id} [{todo.status}] {todo.title}" for todo in open_todos)
                    if open_todos
                    else "No open todos."
                ),
            },
            {
                "role": "system",
                "content": "Recent Messages Block:\n"
                + (
                    "\n".join(
                        f"{message.role}#{message.id}: {message.content}" for message in recent_messages
                    )
                    if recent_messages
                    else "No recent messages."
                ),
            },
            {
                "role": "system",
                "content": "Latest Tool Result Block:\n"
                + (latest_tool_result_summary or "No tool result for this step."),
            },
            {"role": "user", "content": f"Current User Message:\n{current_user_message}"},
        ]
        return messages

