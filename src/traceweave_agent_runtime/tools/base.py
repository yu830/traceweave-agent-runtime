"""Tool primitives."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

from traceweave_agent_runtime.store.sqlite_store import SQLiteStore
from traceweave_agent_runtime.tracing.trace_logger import TraceLogger


@dataclass
class ToolContext:
    user_id: str
    session_id: str
    store: SQLiteStore
    trace_logger: TraceLogger | None = None
    run_id: str = "manual"
    step_index: int = 0
    project_root: Path = Path.cwd()


@dataclass(frozen=True)
class ToolResult:
    data: dict[str, Any]
    summary: str


@dataclass(frozen=True)
class ToolExecutionResult:
    status: str
    data: dict[str, Any]
    summary: str
    error_type: str | None = None
    error_message: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "success"


class ToolHandler(Protocol):
    def __call__(self, arguments: dict[str, Any], context: ToolContext) -> ToolResult:
        ...


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters_schema: dict[str, Any]
    handler: Callable[[dict[str, Any], ToolContext], ToolResult]
    is_read_only: bool = True
    timeout_seconds: int = 5

