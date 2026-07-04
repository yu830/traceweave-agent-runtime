from __future__ import annotations

from traceweave_agent_runtime.tracing.trace_logger import TraceLogger


def test_trace_log_written(store) -> None:
    logger = TraceLogger(store)
    logger.log_event(
        "run",
        "alice",
        "trace",
        1,
        "tool_result",
        "calculator",
        arguments={"expression": "1+1"},
        result={"result": 2},
        result_summary="1+1 = 2",
    )
    traces = store.list_traces("alice", "trace")
    assert len(traces) == 1
    assert traces[0].event_type == "tool_result"
    assert traces[0].result_summary == "1+1 = 2"

