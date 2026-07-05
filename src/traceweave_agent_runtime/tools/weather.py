"""Mock weather tool."""

from __future__ import annotations

from typing import Any

from traceweave_agent_runtime.tools.base import ToolContext, ToolDefinition, ToolResult


WEATHER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "location": {
            "type": "string",
            "description": "Exact city or place from the current user message. Do not invent a default location.",
        },
        "unit": {
            "type": "string",
            "enum": ["celsius", "fahrenheit"],
            "default": "celsius",
            "description": "Temperature unit requested by the user; use celsius when unspecified.",
        },
    },
    "required": ["location"],
    "additionalProperties": False,
}


def weather_handler(arguments: dict[str, Any], context: ToolContext) -> ToolResult:
    del context
    location = arguments["location"]
    unit = arguments.get("unit", "celsius")
    base_celsius = 22 + (sum(ord(char) for char in location) % 11)
    temperature = base_celsius if unit == "celsius" else round(base_celsius * 9 / 5 + 32, 1)
    unit_label = "C" if unit == "celsius" else "F"
    condition = ["sunny", "cloudy", "light rain", "humid"][sum(ord(char) for char in location) % 4]
    return ToolResult(
        data={
            "location": location,
            "temperature": temperature,
            "unit": unit,
            "condition": condition,
            "provider": "mock",
        },
        summary=f"Mock weather for {location}: {temperature} {unit_label}, {condition}.",
    )


def build_weather_tool() -> ToolDefinition:
    return ToolDefinition(
        name="weather",
        description="Return deterministic mock weather for the exact location requested by the user.",
        parameters_schema=WEATHER_SCHEMA,
        handler=weather_handler,
        is_read_only=True,
        timeout_seconds=3,
    )

