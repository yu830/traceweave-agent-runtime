from __future__ import annotations

from pathlib import Path

import pytest

from traceweave_agent_runtime.llm.fake_llm import FakeLLM
from traceweave_agent_runtime.runtime.agent_runtime import (
    AgentRuntime,
    build_default_tool_registry,
)
from traceweave_agent_runtime.store.sqlite_store import SQLiteStore
from traceweave_agent_runtime.tools.base import ToolContext
from traceweave_agent_runtime.tracing.trace_logger import TraceLogger


@pytest.fixture()
def store(tmp_path: Path) -> SQLiteStore:
    sqlite_store = SQLiteStore(tmp_path / "traceweave.sqlite3")
    sqlite_store.init_db()
    return sqlite_store


@pytest.fixture()
def registry():
    return build_default_tool_registry()


@pytest.fixture()
def tool_context(store: SQLiteStore, tmp_path: Path) -> ToolContext:
    return ToolContext(
        user_id="alice",
        session_id="session-a",
        store=store,
        trace_logger=TraceLogger(store),
        run_id="test-run",
        step_index=1,
        project_root=tmp_path,
    )


def make_runtime(
    store: SQLiteStore,
    tmp_path: Path,
    responses: list[str],
    max_steps: int = 5,
    max_recent_messages: int = 12,
) -> AgentRuntime:
    return AgentRuntime(
        store=store,
        llm=FakeLLM(responses),
        tool_registry=build_default_tool_registry(),
        project_root=tmp_path,
        max_steps=max_steps,
        max_recent_messages=max_recent_messages,
        max_context_tokens=6000,
        summary_target_tokens=800,
    )

