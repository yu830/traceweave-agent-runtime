"""Session-scoped todo tool."""

from __future__ import annotations

from typing import Any

from traceweave_agent_runtime.runtime.errors import ToolExecutionError
from traceweave_agent_runtime.tools.base import ToolContext, ToolDefinition, ToolResult


TODO_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "operation": {"type": "string", "enum": ["add", "list", "complete", "update"]},
        "title": {"type": "string"},
        "todo_id": {"type": "integer"},
        "status": {"type": "string", "enum": ["open", "done", "cancelled"]},
    },
    "required": ["operation"],
    "additionalProperties": False,
}


def todo_handler(arguments: dict[str, Any], context: ToolContext) -> ToolResult:
    operation = arguments["operation"]
    if operation == "add":
        title = arguments.get("title")
        if not title:
            raise ToolExecutionError("todo.add requires title")
        todo = context.store.add_todo(context.user_id, context.session_id, title)
        return ToolResult(
            data={"todo": todo.__dict__},
            summary=f"Added todo #{todo.id}: {todo.title}",
        )
    if operation == "list":
        todos = context.store.list_todos(context.user_id, context.session_id)
        return ToolResult(
            data={"todos": [todo.__dict__ for todo in todos]},
            summary=f"Found {len(todos)} todos in this session.",
        )
    if operation == "complete":
        todo_id = arguments.get("todo_id")
        if todo_id is None:
            raise ToolExecutionError("todo.complete requires todo_id")
        todo = context.store.update_todo(context.user_id, context.session_id, int(todo_id), status="done")
        if todo is None:
            raise ToolExecutionError(f"Todo not found: {todo_id}")
        return ToolResult(
            data={"todo": todo.__dict__},
            summary=f"Completed todo #{todo.id}: {todo.title}",
        )
    if operation == "update":
        todo_id = arguments.get("todo_id")
        if todo_id is None:
            raise ToolExecutionError("todo.update requires todo_id")
        title = arguments.get("title")
        status = arguments.get("status")
        if title is None and status is None:
            raise ToolExecutionError("todo.update requires title or status")
        todo = context.store.update_todo(
            context.user_id,
            context.session_id,
            int(todo_id),
            title=title,
            status=status,
        )
        if todo is None:
            raise ToolExecutionError(f"Todo not found: {todo_id}")
        return ToolResult(
            data={"todo": todo.__dict__},
            summary=f"Updated todo #{todo.id}: {todo.title} [{todo.status}]",
        )
    raise ToolExecutionError(f"Unsupported todo operation: {operation}")


def build_todo_tool() -> ToolDefinition:
    return ToolDefinition(
        name="todo",
        description="Manage session-scoped todos. Supports add, list, complete, and update.",
        parameters_schema=TODO_SCHEMA,
        handler=todo_handler,
        is_read_only=False,
        timeout_seconds=5,
    )

