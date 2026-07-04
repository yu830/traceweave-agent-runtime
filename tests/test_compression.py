from __future__ import annotations

from traceweave_agent_runtime.runtime.compression import DeterministicCompressor
from traceweave_agent_runtime.runtime.context_builder import ContextBuilder


def test_context_compression_triggers(store) -> None:
    for index in range(15):
        store.add_message("alice", "compress", "user", f"message {index}")
    compressor = DeterministicCompressor(store, max_recent_messages=12)
    summary = compressor.compress_if_needed("alice", "compress")
    assert summary is not None
    assert "Important facts" in summary.summary_text
    assert store.count_messages("alice", "compress", include_summarized=False) == 12


def test_context_compression_preserves_open_todos_in_state(store, registry) -> None:
    store.add_todo("alice", "compress-state", "keep umbrella todo")
    for index in range(14):
        store.add_message("alice", "compress-state", "user", f"message {index}")
    compressor = DeterministicCompressor(store, max_recent_messages=10)
    summary = compressor.compress_if_needed("alice", "compress-state")
    assert summary is not None
    assert "keep umbrella todo" in summary.summary_text
    context = ContextBuilder(store, registry, max_recent_messages=10).build(
        "alice",
        "compress-state",
        "what remains?",
    )
    joined = "\n".join(message["content"] for message in context)
    assert "keep umbrella todo" in joined
    assert "Session Summary Block" in joined

