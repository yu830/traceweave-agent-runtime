"""Self-built tool registry with JSON Schema validation and trace logging."""

from __future__ import annotations

import re
import time
from typing import Any

from jsonschema import Draft7Validator, ValidationError

from traceweave_agent_runtime.runtime.errors import (
    ToolArgumentValidationError,
    ToolExecutionError,
    ToolNotFoundError,
)
from traceweave_agent_runtime.tools.base import (
    ToolContext,
    ToolDefinition,
    ToolExecutionResult,
)


class ToolRegistry:
    _name_re = re.compile(r"^[a-z0-9_]+$")

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        if not self._name_re.match(tool.name):
            raise ValueError("Tool name must contain only lowercase letters, digits, and underscores")
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        Draft7Validator.check_schema(tool.parameters_schema)
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolNotFoundError(f"Tool not found: {name}") from exc

    def list_tools(self) -> list[ToolDefinition]:
        return [self._tools[name] for name in sorted(self._tools)]

    def list_schemas_for_llm(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters_schema": tool.parameters_schema,
                "is_read_only": tool.is_read_only,
            }
            for tool in self.list_tools()
        ]

    def validate_arguments(self, tool_name: str, arguments: dict[str, Any]) -> None:
        tool = self.get(tool_name)
        validator = Draft7Validator(tool.parameters_schema)
        errors = sorted(validator.iter_errors(arguments), key=lambda error: list(error.path))
        if errors:
            message = "; ".join(self._format_schema_error(error) for error in errors)
            raise ToolArgumentValidationError(f"Invalid arguments for {tool_name}: {message}")

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: ToolContext,
    ) -> ToolExecutionResult:
        started = time.perf_counter()
        try:
            tool = self.get(tool_name)
        except ToolNotFoundError as exc:
            result = ToolExecutionResult(
                status="error",
                data={},
                summary=f"Tool not found: {tool_name}",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            self._log(context, "tool_error", tool_name, arguments, result, self._latency(started))
            return result

        self._log(
            context,
            "tool_call",
            tool.name,
            arguments,
            ToolExecutionResult("started", {}, f"Calling tool {tool.name}"),
            0,
        )
        try:
            self.validate_arguments(tool.name, arguments)
            tool_result = tool.handler(arguments, context)
            result = ToolExecutionResult(
                status="success",
                data=tool_result.data,
                summary=tool_result.summary,
            )
            self._log(context, "tool_result", tool.name, arguments, result, self._latency(started))
            return result
        except (ToolArgumentValidationError, ToolExecutionError) as exc:
            result = ToolExecutionResult(
                status="error",
                data={},
                summary=f"{tool.name} failed: {exc}",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            self._log(context, "tool_error", tool.name, arguments, result, self._latency(started))
            return result
        except Exception as exc:  # noqa: BLE001 - tool isolation boundary.
            wrapped = ToolExecutionError(f"{tool.name} execution failed: {exc}")
            result = ToolExecutionResult(
                status="error",
                data={},
                summary=str(wrapped),
                error_type=type(wrapped).__name__,
                error_message=str(wrapped),
            )
            self._log(context, "tool_error", tool.name, arguments, result, self._latency(started))
            return result

    @staticmethod
    def _format_schema_error(error: ValidationError) -> str:
        location = ".".join(str(part) for part in error.path) or "<root>"
        return f"{location}: {error.message}"

    @staticmethod
    def _latency(started: float) -> int:
        return int((time.perf_counter() - started) * 1000)

    @staticmethod
    def _log(
        context: ToolContext,
        event_type: str,
        tool_name: str,
        arguments: dict[str, Any],
        result: ToolExecutionResult,
        latency_ms: int,
    ) -> None:
        if context.trace_logger is None:
            return
        context.trace_logger.log_event(
            run_id=context.run_id,
            user_id=context.user_id,
            session_id=context.session_id,
            step_index=context.step_index,
            event_type=event_type,
            tool_name=tool_name,
            arguments=arguments,
            result=result.data,
            result_summary=result.summary,
            status=result.status,
            error_type=result.error_type,
            error_message=result.error_message,
            latency_ms=latency_ms,
        )

