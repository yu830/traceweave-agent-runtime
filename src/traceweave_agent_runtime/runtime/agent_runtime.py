"""Self-built minimal agent runtime loop."""

from __future__ import annotations

import time
import uuid
from pathlib import Path

from traceweave_agent_runtime.config import RuntimeConfig
from traceweave_agent_runtime.llm.base import BaseLLM
from traceweave_agent_runtime.llm.openai_compatible import OpenAICompatibleLLM
from traceweave_agent_runtime.runtime.compression import DeterministicCompressor
from traceweave_agent_runtime.runtime.context_builder import ContextBuilder
from traceweave_agent_runtime.runtime.errors import (
    LLMAPIError,
    LLMOutputParseError,
    LLMOutputValidationError,
)
from traceweave_agent_runtime.runtime.parser import ActionParser
from traceweave_agent_runtime.store.sqlite_store import SQLiteStore
from traceweave_agent_runtime.tools.base import ToolContext
from traceweave_agent_runtime.tools.calculator import build_calculator_tool
from traceweave_agent_runtime.tools.datetime_tool import build_datetime_tool
from traceweave_agent_runtime.tools.note import build_note_tool
from traceweave_agent_runtime.tools.read_docs import build_read_docs_tool
from traceweave_agent_runtime.tools.registry import ToolRegistry
from traceweave_agent_runtime.tools.search import build_search_tool
from traceweave_agent_runtime.tools.todo import build_todo_tool
from traceweave_agent_runtime.tools.weather import build_weather_tool
from traceweave_agent_runtime.tracing.trace_logger import TraceLogger


class AgentRuntime:
    def __init__(
        self,
        store: SQLiteStore,
        llm: BaseLLM,
        tool_registry: ToolRegistry,
        project_root: Path,
        max_steps: int = 5,
        max_recent_messages: int = 12,
        max_context_tokens: int = 6000,
        summary_target_tokens: int = 800,
    ) -> None:
        self.store = store
        self.llm = llm
        self.tool_registry = tool_registry
        self.project_root = project_root
        self.max_steps = max_steps
        self.max_recent_messages = max_recent_messages
        self.max_context_tokens = max_context_tokens
        self.summary_target_tokens = summary_target_tokens
        self.parser = ActionParser()
        self.trace_logger = TraceLogger(store)
        self.context_builder = ContextBuilder(store, tool_registry, max_recent_messages)
        self.compressor = DeterministicCompressor(
            store,
            max_recent_messages=max_recent_messages,
            max_context_tokens=max_context_tokens,
            summary_target_tokens=summary_target_tokens,
        )

    def run_turn(self, user_id: str, session_id: str, user_input: str) -> str:
        run_id = str(uuid.uuid4())
        self.store.upsert_session(
            user_id,
            session_id,
            max_context_tokens=self.max_context_tokens,
            max_recent_messages=self.max_recent_messages,
        )
        current_message = self.store.add_message(user_id, session_id, "user", user_input)
        self.compressor.compress_if_needed(user_id, session_id, run_id, self.trace_logger)
        tool_result_summaries: list[str] = []
        raw_response = ""
        for step_index in range(1, self.max_steps + 1):
            messages = self.context_builder.build(
                user_id,
                session_id,
                user_input,
                current_message_id=current_message.id,
                tool_result_summaries=tool_result_summaries,
            )
            self.trace_logger.llm_request(run_id, user_id, session_id, step_index, messages)
            started = time.perf_counter()
            try:
                raw_response = self.llm.complete(messages)
            except LLMAPIError as exc:
                self.trace_logger.log_event(
                    run_id,
                    user_id,
                    session_id,
                    step_index,
                    "llm_response",
                    "__llm__",
                    status="error",
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    result_summary="LLM API call failed",
                )
                answer = f"LLM API error: {exc}"
                self.store.add_message(user_id, session_id, "assistant", answer)
                return answer
            latency_ms = int((time.perf_counter() - started) * 1000)
            self.trace_logger.llm_response(run_id, user_id, session_id, step_index, raw_response, latency_ms)
            try:
                action = self.parser.parse(raw_response)
            except (LLMOutputParseError, LLMOutputValidationError) as exc:
                self.trace_logger.parser_error(run_id, user_id, session_id, step_index, exc, raw_response)
                answer = f"I could not parse the model response as a valid runtime action: {exc}"
                self.store.add_message(user_id, session_id, "assistant", answer)
                return answer
            if action.action == "final_answer":
                answer = action.final_answer or ""
                self.store.add_message(user_id, session_id, "assistant", answer)
                self.trace_logger.log_event(
                    run_id,
                    user_id,
                    session_id,
                    step_index,
                    "final_answer",
                    "__runtime__",
                    result={"reasoning_summary": action.reasoning_summary},
                    result_summary=answer[:500],
                )
                return answer
            assert action.tool_call is not None
            context = ToolContext(
                user_id=user_id,
                session_id=session_id,
                store=self.store,
                trace_logger=self.trace_logger,
                run_id=run_id,
                step_index=step_index,
                project_root=self.project_root,
            )
            result = self.tool_registry.execute(
                action.tool_call.name,
                action.tool_call.arguments,
                context,
            )
            tool_result_summaries.append(f"{action.tool_call.name}: {result.summary}")
            if not result.ok:
                answer = f"Tool execution failed in a recoverable way: {result.summary}"
                self.store.add_message(user_id, session_id, "assistant", answer)
                return answer
        self.trace_logger.log_event(
            run_id,
            user_id,
            session_id,
            self.max_steps,
            "max_steps_reached",
            "__runtime__",
            result={"last_response": raw_response[:1000]},
            result_summary=f"Agent exceeded max_steps={self.max_steps}.",
            status="error",
            error_type="MaxStepsExceededError",
            error_message=f"Agent exceeded max_steps={self.max_steps}.",
        )
        answer = f"Agent stopped because it exceeded max_steps={self.max_steps}."
        self.store.add_message(user_id, session_id, "assistant", answer)
        return answer


def build_default_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(build_calculator_tool())
    registry.register(build_search_tool())
    registry.register(build_todo_tool())
    registry.register(build_weather_tool())
    registry.register(build_read_docs_tool())
    registry.register(build_datetime_tool())
    registry.register(build_note_tool())
    return registry


def build_runtime_from_env(project_root: Path | None = None) -> AgentRuntime:
    root = project_root or Path.cwd()
    config = RuntimeConfig.from_env(root)
    store = SQLiteStore(config.db_path)
    store.init_db()
    llm = OpenAICompatibleLLM(config)
    return AgentRuntime(
        store=store,
        llm=llm,
        tool_registry=build_default_tool_registry(),
        project_root=root,
        max_steps=config.max_steps,
        max_recent_messages=config.max_recent_messages,
        max_context_tokens=config.max_context_tokens,
        summary_target_tokens=config.summary_target_tokens,
    )

