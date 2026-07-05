from __future__ import annotations

import threading
from pathlib import Path

import httpx

from conftest import make_runtime
from traceweave_agent_runtime.web_app import HTML_PAGE, TraceWeaveHTTPServer


def test_web_page_contains_chat_surface() -> None:
    assert "TraceWeave" in HTML_PAGE
    assert "/api/chat" in HTML_PAGE
    assert "/api/todos" in HTML_PAGE
    assert "/api/traces" in HTML_PAGE


def test_web_chat_api_runs_runtime(store, tmp_path: Path) -> None:
    runtime = make_runtime(
        store,
        tmp_path,
        [
            '{"action":"final_answer","reasoning_summary":"Reply directly.",'
            '"tool_call":null,"final_answer":"web ok"}'
        ],
    )
    server = TraceWeaveHTTPServer(("127.0.0.1", 0), runtime, store)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        response = httpx.post(
            f"{base_url}/api/chat",
            json={"user_id": "alice", "session_id": "web", "message": "hello"},
            timeout=5,
        )
        assert response.status_code == 200
        assert response.json()["answer"] == "web ok"

        traces = httpx.get(
            f"{base_url}/api/traces",
            params={"user_id": "alice", "session_id": "web"},
            timeout=5,
        )
        assert traces.status_code == 200
        assert any(trace["event_type"] == "final_answer" for trace in traces.json()["traces"])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
