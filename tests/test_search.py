from __future__ import annotations

from traceweave_agent_runtime.tools.search import RealSearchAdapter, search_handler


def test_search_mock_fallback_for_invalid_provider(monkeypatch, tool_context) -> None:
    monkeypatch.setenv("SEARCH_PROVIDER", "unknown")
    result = search_handler({"query": "agent runtime", "top_k": 2}, tool_context)
    assert result.data["adapter"] == "MockSearchAdapter"
    assert len(result.data["results"]) == 2
    traces = tool_context.store.list_traces(tool_context.user_id, tool_context.session_id)
    assert any(trace.status == "fallback" for trace in traces)


def test_search_real_adapter_exception_fallback_mock(monkeypatch, tool_context) -> None:
    monkeypatch.setenv("SEARCH_PROVIDER", "real")
    monkeypatch.setenv("SEARCH_API_KEY", "test-key")
    monkeypatch.setenv("SEARCH_ENDPOINT", "https://search.invalid")

    def boom(self, query: str, top_k: int):
        del self, query, top_k
        raise RuntimeError("network failed")

    monkeypatch.setattr(RealSearchAdapter, "search", boom)
    result = search_handler({"query": "trace", "top_k": 1}, tool_context)
    assert result.data["adapter"] == "MockSearchAdapter"
    assert "Mock result" in result.data["results"][0]["title"]

