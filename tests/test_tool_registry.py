from __future__ import annotations

import pytest

from traceweave_agent_runtime.tools.base import ToolContext, ToolDefinition, ToolResult
from traceweave_agent_runtime.tools.registry import ToolRegistry


def _echo_tool() -> ToolDefinition:
    def handler(arguments, context: ToolContext) -> ToolResult:
        del context
        return ToolResult(data={"value": arguments["value"]}, summary=arguments["value"])

    return ToolDefinition(
        name="echo",
        description="Echo a value.",
        parameters_schema={
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
            "additionalProperties": False,
        },
        handler=handler,
    )


def test_tool_registry_register_and_get() -> None:
    registry = ToolRegistry()
    registry.register(_echo_tool())
    assert registry.get("echo").name == "echo"
    assert registry.list_schemas_for_llm()[0]["name"] == "echo"


def test_tool_registry_duplicate_register_raises() -> None:
    registry = ToolRegistry()
    registry.register(_echo_tool())
    with pytest.raises(ValueError):
        registry.register(_echo_tool())

