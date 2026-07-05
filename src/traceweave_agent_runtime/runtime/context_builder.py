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
If calling a tool, final_answer must be null. If answering, tool_call must be null.
Extract tool arguments from the Current User Message exactly. Never invent
default cities, dates, todo titles, or document paths when the user provided
them. For mixed requests, complete each requested tool action once, then answer.
Before calling a tool, check the Tool Results Block. Do not repeat a tool call
that already returned the needed information in this turn. When all requested
tool work is complete, return final_answer."""


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
        tool_result_summaries: list[str] | None = None,
    ) -> list[dict[str, str]]:
        summary = self.store.get_latest_summary(user_id, session_id)
        open_todos = self.store.list_todos(user_id, session_id, status="open")
        recent_messages = self.store.list_recent_messages(
            user_id,
            session_id,
            limit=self.max_recent_messages,
            exclude_message_id=current_message_id,
        )
        tool_results = list(tool_result_summaries or [])
        if latest_tool_result_summary and latest_tool_result_summary not in tool_results:
            tool_results.append(latest_tool_result_summary)
        tool_results_block = (
            "\n".join(f"- {summary}" for summary in tool_results)
            if tool_results
            else "No tool result for this step."
        )
        current_user_content = f"Current User Message:\n{current_user_message}"
        if tool_results:
            current_user_content += (
                "\n\nTool Results Already Available For This Turn:\n"
                + tool_results_block
                + "\n\nUse these results. Do not call completed tools again. "
                "If another requested side effect is still missing, call that tool next; "
                "otherwise return final_answer."
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
                "content": "Tool Results Block:\n" + tool_results_block,
            },
            {"role": "user", "content": current_user_content},
        ]
        return messages

