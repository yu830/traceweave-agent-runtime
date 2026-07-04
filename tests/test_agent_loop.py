from __future__ import annotations

from pathlib import Path

from conftest import make_runtime


def _final(text: str = "done") -> str:
    return (
        '{"action":"final_answer","reasoning_summary":"Ready to answer.",'
        f'"tool_call":null,"final_answer":"{text}"}}'
    )


def _tool(name: str, arguments: str) -> str:
    return (
        '{"action":"tool_call","reasoning_summary":"Need a tool.",'
        f'"tool_call":{{"name":"{name}","arguments":{arguments}}},"final_answer":null}}'
    )


def test_agent_loop_direct_answer(store, tmp_path: Path) -> None:
    runtime = make_runtime(store, tmp_path, [_final("direct answer")])
    assert runtime.run_turn("alice", "direct", "hello") == "direct answer"
    messages = store.list_messages("alice", "direct")
    assert messages[-1].role == "assistant"


def test_agent_loop_tool_call_then_final_answer(store, tmp_path: Path) -> None:
    runtime = make_runtime(
        store,
        tmp_path,
        [_tool("calculator", '{"expression":"1+2"}'), _final("The answer is 3.")],
    )
    assert runtime.run_turn("alice", "tool", "calculate") == "The answer is 3."
    traces = store.list_traces("alice", "tool")
    assert any(trace.event_type == "tool_result" and trace.tool_name == "calculator" for trace in traces)
    assert len(runtime.llm.requests) == 2
    assert "1+2 = 3" in "\n".join(message["content"] for message in runtime.llm.requests[1])


def test_max_steps_prevents_infinite_loop(store, tmp_path: Path) -> None:
    runtime = make_runtime(
        store,
        tmp_path,
        [
            _tool("calculator", '{"expression":"1+1"}'),
            _tool("calculator", '{"expression":"2+2"}'),
            _tool("calculator", '{"expression":"3+3"}'),
        ],
        max_steps=2,
    )
    answer = runtime.run_turn("alice", "loop", "keep going")
    assert "exceeded max_steps=2" in answer
    assert any(trace.event_type == "max_steps_reached" for trace in store.list_traces("alice", "loop"))


def test_tool_error_recorded_and_user_gets_understandable_error(store, tmp_path: Path) -> None:
    runtime = make_runtime(
        store,
        tmp_path,
        [_tool("calculator", '{"expression":"__import__(\\"os\\")"}')],
    )
    answer = runtime.run_turn("alice", "tool-error", "do unsafe thing")
    assert "Tool execution failed" in answer
    traces = store.list_traces("alice", "tool-error")
    assert any(trace.event_type == "tool_error" and trace.tool_name == "calculator" for trace in traces)

