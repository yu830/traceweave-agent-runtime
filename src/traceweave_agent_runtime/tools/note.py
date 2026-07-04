"""Session-scoped note tool."""

from __future__ import annotations

from typing import Any

from traceweave_agent_runtime.runtime.errors import ToolExecutionError
from traceweave_agent_runtime.tools.base import ToolContext, ToolDefinition, ToolResult


NOTE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "operation": {"type": "string", "enum": ["add", "list"]},
        "content": {"type": "string"},
    },
    "required": ["operation"],
    "additionalProperties": False,
}


def note_handler(arguments: dict[str, Any], context: ToolContext) -> ToolResult:
    operation = arguments["operation"]
    if operation == "add":
        content = arguments.get("content")
        if not content:
            raise ToolExecutionError("note.add requires content")
        note = context.store.add_note(context.user_id, context.session_id, content)
        return ToolResult(data={"note": note.__dict__}, summary=f"Added note #{note.id}.")
    if operation == "list":
        notes = context.store.list_notes(context.user_id, context.session_id)
        return ToolResult(
            data={"notes": [note.__dict__ for note in notes]},
            summary=f"Found {len(notes)} notes in this session.",
        )
    raise ToolExecutionError(f"Unsupported note operation: {operation}")


def build_note_tool() -> ToolDefinition:
    return ToolDefinition(
        name="note",
        description="Manage session-scoped notes. Supports add and list.",
        parameters_schema=NOTE_SCHEMA,
        handler=note_handler,
        is_read_only=False,
        timeout_seconds=3,
    )

