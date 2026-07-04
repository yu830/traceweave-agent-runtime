"""Search tool with stable mock behavior and optional real adapter fallback."""

from __future__ import annotations

import os
from typing import Any, Protocol

import httpx

from traceweave_agent_runtime.tools.base import ToolContext, ToolDefinition, ToolResult


SEARCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {"type": "string"},
        "top_k": {"type": "integer", "minimum": 1, "maximum": 5, "default": 3},
    },
    "required": ["query"],
    "additionalProperties": False,
}


class SearchAdapter(Protocol):
    def search(self, query: str, top_k: int) -> list[dict[str, str]]:
        ...


class MockSearchAdapter:
    def search(self, query: str, top_k: int) -> list[dict[str, str]]:
        return [
            {
                "title": f"Mock result {index} for {query}",
                "url": f"https://example.com/search/{index}",
                "snippet": f"Deterministic mock search snippet {index} about {query}.",
            }
            for index in range(1, top_k + 1)
        ]


class RealSearchAdapter:
    def __init__(self, endpoint: str, api_key: str, timeout_seconds: float):
        self.endpoint = endpoint
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def search(self, query: str, top_k: int) -> list[dict[str, str]]:
        response = httpx.get(
            self.endpoint,
            params={"q": query, "top_k": top_k},
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        raw_results = payload.get("results", payload if isinstance(payload, list) else [])
        results: list[dict[str, str]] = []
        for item in raw_results[:top_k]:
            results.append(
                {
                    "title": str(item.get("title", "Untitled")),
                    "url": str(item.get("url", "")),
                    "snippet": str(item.get("snippet", item.get("summary", ""))),
                }
            )
        return results


def _log_search_fallback(context: ToolContext, reason: str) -> None:
    if context.trace_logger is None:
        return
    context.trace_logger.log_event(
        run_id=context.run_id,
        user_id=context.user_id,
        session_id=context.session_id,
        step_index=context.step_index,
        event_type="tool_error",
        tool_name="search",
        arguments={"fallback_reason": reason},
        result={"fallback": "mock"},
        result_summary="Search fallback to MockSearchAdapter",
        status="fallback",
        error_type="SearchFallback",
        error_message=reason,
    )


def _select_adapter(context: ToolContext) -> SearchAdapter:
    provider = os.getenv("SEARCH_PROVIDER", "mock").strip().lower() or "mock"
    top_provider_names = {"real", "http", "generic"}
    if provider == "mock":
        return MockSearchAdapter()
    if provider not in top_provider_names:
        _log_search_fallback(context, f"Unsupported SEARCH_PROVIDER={provider!r}")
        return MockSearchAdapter()
    api_key = os.getenv("SEARCH_API_KEY", "")
    endpoint = os.getenv("SEARCH_ENDPOINT", "")
    if not api_key or not endpoint:
        _log_search_fallback(context, "SEARCH_API_KEY or SEARCH_ENDPOINT is missing")
        return MockSearchAdapter()
    timeout_seconds = float(os.getenv("SEARCH_TIMEOUT_SECONDS", "5"))
    return RealSearchAdapter(endpoint=endpoint, api_key=api_key, timeout_seconds=timeout_seconds)


def search_handler(arguments: dict[str, Any], context: ToolContext) -> ToolResult:
    query = arguments["query"]
    top_k = int(arguments.get("top_k", 3))
    adapter = _select_adapter(context)
    try:
        results = adapter.search(query, top_k)
        adapter_name = type(adapter).__name__
    except Exception as exc:  # noqa: BLE001 - network fallback boundary.
        _log_search_fallback(context, f"Real search adapter failed: {exc}")
        results = MockSearchAdapter().search(query, top_k)
        adapter_name = "MockSearchAdapter"
    return ToolResult(
        data={"query": query, "top_k": top_k, "adapter": adapter_name, "results": results},
        summary=f"Search returned {len(results)} results for {query} using {adapter_name}.",
    )


def build_search_tool() -> ToolDefinition:
    return ToolDefinition(
        name="search",
        description="Search the web. Defaults to deterministic mock results; real search is optional.",
        parameters_schema=SEARCH_SCHEMA,
        handler=search_handler,
        is_read_only=True,
        timeout_seconds=5,
    )

