"""Datetime tool."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from traceweave_agent_runtime.runtime.errors import ToolExecutionError
from traceweave_agent_runtime.tools.base import ToolContext, ToolDefinition, ToolResult


DATETIME_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "timezone": {"type": "string", "default": "Asia/Singapore"},
        "format": {"type": "string", "enum": ["date", "time", "datetime"], "default": "datetime"},
    },
    "required": [],
    "additionalProperties": False,
}


def datetime_handler(arguments: dict[str, Any], context: ToolContext) -> ToolResult:
    del context
    timezone_name = arguments.get("timezone", "Asia/Singapore")
    output_format = arguments.get("format", "datetime")
    try:
        now = datetime.now(ZoneInfo(timezone_name))
    except ZoneInfoNotFoundError as exc:
        raise ToolExecutionError(f"Unknown timezone: {timezone_name}") from exc
    if output_format == "date":
        value = now.date().isoformat()
    elif output_format == "time":
        value = now.strftime("%H:%M:%S")
    else:
        value = now.replace(microsecond=0).isoformat()
    return ToolResult(
        data={"timezone": timezone_name, "format": output_format, "value": value},
        summary=f"Current {output_format} in {timezone_name}: {value}",
    )


def build_datetime_tool() -> ToolDefinition:
    return ToolDefinition(
        name="datetime",
        description="Return the current date, time, or datetime for an IANA timezone.",
        parameters_schema=DATETIME_SCHEMA,
        handler=datetime_handler,
        is_read_only=True,
        timeout_seconds=2,
    )

