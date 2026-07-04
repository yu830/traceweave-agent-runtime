from __future__ import annotations

from traceweave_agent_runtime.runtime.context_builder import ContextBuilder


def test_context_builder_includes_tool_schema_summary_recent_messages(store, registry) -> None:
    store.add_summary("alice", "ctx", "Past summary: user asked about runtime.", 1, 2, "test")
    store.add_todo("alice", "ctx", "write docs")
    msg = store.add_message("alice", "ctx", "user", "older user message")
    builder = ContextBuilder(store, registry, max_recent_messages=5)
    context = builder.build(
        "alice",
        "ctx",
        "current question",
        current_message_id=msg.id + 1,
        latest_tool_result_summary="calculator returned 4",
    )
    joined = "\n".join(item["content"] for item in context)
    assert "Tool Schema Block" in joined
    assert "calculator" in joined
    assert "Past summary" in joined
    assert "older user message" in joined
    assert "calculator returned 4" in joined

