"""Restricted project-doc reader tool."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from traceweave_agent_runtime.runtime.errors import ToolExecutionError
from traceweave_agent_runtime.tools.base import ToolContext, ToolDefinition, ToolResult


READ_DOCS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "path": {"type": "string"},
        "max_chars": {"type": "integer", "minimum": 200, "maximum": 4000, "default": 1200},
    },
    "required": ["path"],
    "additionalProperties": False,
}


def read_docs_handler(arguments: dict[str, Any], context: ToolContext) -> ToolResult:
    raw_path = arguments["path"]
    max_chars = int(arguments.get("max_chars", 1200))
    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise ToolExecutionError("read_docs does not allow absolute paths")
    if ".." in candidate.parts:
        raise ToolExecutionError("read_docs does not allow parent directory traversal")
    allowed_roots = [
        (context.project_root / "docs").resolve(),
        (context.project_root / "examples" / "sample_docs").resolve(),
    ]
    resolved = (context.project_root / candidate).resolve()
    if not any(resolved == root or root in resolved.parents for root in allowed_roots):
        raise ToolExecutionError("read_docs can only read docs/ or examples/sample_docs/")
    if not resolved.is_file():
        raise ToolExecutionError(f"Document not found: {raw_path}")
    content = resolved.read_text(encoding="utf-8")
    truncated = len(content) > max_chars
    snippet = content[:max_chars]
    return ToolResult(
        data={"path": raw_path, "content": snippet, "truncated": truncated},
        summary=f"Read {len(snippet)} chars from {raw_path}; truncated={truncated}.",
    )


def build_read_docs_tool() -> ToolDefinition:
    return ToolDefinition(
        name="read_docs",
        description="Read a project doc from docs/ or examples/sample_docs/ with max_chars truncation.",
        parameters_schema=READ_DOCS_SCHEMA,
        handler=read_docs_handler,
        is_read_only=True,
        timeout_seconds=3,
    )

