"""Small local web UI for the TraceWeave runtime."""

from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from traceweave_agent_runtime.runtime.agent_runtime import AgentRuntime, build_runtime_from_env
from traceweave_agent_runtime.runtime.errors import ConfigError
from traceweave_agent_runtime.store.sqlite_store import SQLiteStore


HTML_PAGE = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TraceWeave</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f7f4ef;
      --panel: #fffdfa;
      --line: #d8d0c3;
      --text: #211f1b;
      --muted: #6f675d;
      --accent: #0f6a5f;
      --accent-strong: #084b44;
      --warn: #a64728;
      --shadow: 0 18px 45px rgba(48, 39, 25, 0.12);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: "Yu Serif Codex", "Yu Serif Text", "Yu Serif", Georgia, serif;
    }

    button, input, textarea {
      font: inherit;
    }

    .app {
      display: grid;
      grid-template-columns: minmax(220px, 280px) minmax(0, 1fr) minmax(260px, 340px);
      min-height: 100vh;
    }

    aside, main {
      padding: 22px;
    }

    aside {
      border-right: 1px solid var(--line);
      background: rgba(255, 253, 250, 0.72);
    }

    .right {
      border-right: 0;
      border-left: 1px solid var(--line);
    }

    h1, h2 {
      margin: 0;
      font-weight: 700;
      letter-spacing: 0;
    }

    h1 {
      font-size: 28px;
      line-height: 1.1;
    }

    h2 {
      font-size: 16px;
      margin-bottom: 10px;
    }

    label {
      display: block;
      margin: 18px 0 7px;
      color: var(--muted);
      font-size: 13px;
    }

    input, textarea {
      width: 100%;
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--text);
      border-radius: 7px;
      padding: 10px 11px;
      outline: none;
    }

    input:focus, textarea:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(15, 106, 95, 0.14);
    }

    .chat {
      display: flex;
      flex-direction: column;
      min-height: 100vh;
      padding: 22px min(4vw, 46px);
    }

    .messages {
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 12px;
      overflow: auto;
      padding: 24px 0;
    }

    .bubble {
      max-width: min(760px, 92%);
      padding: 13px 15px;
      border-radius: 8px;
      border: 1px solid var(--line);
      background: var(--panel);
      box-shadow: 0 8px 20px rgba(48, 39, 25, 0.06);
      line-height: 1.55;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }

    .bubble.user {
      align-self: flex-end;
      border-color: rgba(15, 106, 95, 0.28);
      background: #eef8f4;
    }

    .bubble.assistant {
      align-self: flex-start;
    }

    .composer {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 10px;
      align-items: end;
      padding: 16px 0 4px;
      border-top: 1px solid var(--line);
    }

    textarea {
      min-height: 58px;
      resize: vertical;
    }

    button {
      border: 0;
      border-radius: 7px;
      padding: 11px 17px;
      background: var(--accent);
      color: white;
      cursor: pointer;
      min-height: 42px;
    }

    button:hover {
      background: var(--accent-strong);
    }

    button.secondary {
      width: 100%;
      margin-top: 10px;
      background: #e8e0d4;
      color: var(--text);
    }

    button.secondary:hover {
      background: #ded4c5;
    }

    .status {
      min-height: 22px;
      margin-top: 16px;
      color: var(--muted);
      font-size: 13px;
    }

    .status.error {
      color: var(--warn);
    }

    .list {
      display: flex;
      flex-direction: column;
      gap: 8px;
      max-height: 36vh;
      overflow: auto;
      padding-right: 4px;
    }

    .row {
      padding: 9px 10px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: var(--panel);
      font-size: 13px;
      line-height: 1.4;
      overflow-wrap: anywhere;
    }

    .section {
      margin-top: 24px;
    }

    @media (max-width: 960px) {
      .app {
        grid-template-columns: 1fr;
      }

      aside, .right {
        border: 0;
        border-bottom: 1px solid var(--line);
      }

      .chat {
        min-height: 68vh;
      }

      .composer {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <div class="app">
    <aside>
      <h1>TraceWeave</h1>
      <label for="userId">User</label>
      <input id="userId" value="alice" autocomplete="off">
      <label for="sessionId">Session</label>
      <input id="sessionId" value="weather" autocomplete="off">
      <button class="secondary" id="refreshButton" type="button">Refresh State</button>
      <div id="status" class="status"></div>
    </aside>

    <main class="chat">
      <div id="messages" class="messages"></div>
      <form id="chatForm" class="composer">
        <textarea id="messageInput" placeholder="输入消息..." required></textarea>
        <button id="sendButton" type="submit">Send</button>
      </form>
    </main>

    <aside class="right">
      <div class="section">
        <h2>Todos</h2>
        <div id="todos" class="list"></div>
      </div>
      <div class="section">
        <h2>Trace</h2>
        <div id="traces" class="list"></div>
      </div>
    </aside>
  </div>

  <script>
    const userId = document.getElementById("userId");
    const sessionId = document.getElementById("sessionId");
    const statusEl = document.getElementById("status");
    const messagesEl = document.getElementById("messages");
    const todosEl = document.getElementById("todos");
    const tracesEl = document.getElementById("traces");
    const messageInput = document.getElementById("messageInput");
    const sendButton = document.getElementById("sendButton");

    function setStatus(text, isError = false) {
      statusEl.textContent = text;
      statusEl.className = isError ? "status error" : "status";
    }

    function addBubble(role, text) {
      const div = document.createElement("div");
      div.className = `bubble ${role}`;
      div.textContent = text;
      messagesEl.appendChild(div);
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function renderRows(el, rows, emptyText, render) {
      el.replaceChildren();
      if (!rows.length) {
        const empty = document.createElement("div");
        empty.className = "row";
        empty.textContent = emptyText;
        el.appendChild(empty);
        return;
      }
      for (const row of rows) {
        const div = document.createElement("div");
        div.className = "row";
        div.textContent = render(row);
        el.appendChild(div);
      }
    }

    async function api(path, options = {}) {
      const res = await fetch(path, {
        headers: {"Content-Type": "application/json"},
        ...options
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || `HTTP ${res.status}`);
      }
      return data;
    }

    async function refreshState() {
      const params = new URLSearchParams({user_id: userId.value, session_id: sessionId.value});
      const [todos, traces] = await Promise.all([
        api(`/api/todos?${params}`),
        api(`/api/traces?${params}`)
      ]);
      renderRows(todosEl, todos.todos, "No todos.", todo => `#${todo.id} [${todo.status}] ${todo.title}`);
      renderRows(tracesEl, traces.traces.slice(-12), "No traces.", trace =>
        `${trace.step_index} ${trace.event_type} ${trace.tool_name}: ${trace.result_summary}`
      );
    }

    async function sendMessage(event) {
      event.preventDefault();
      const text = messageInput.value.trim();
      if (!text) return;
      addBubble("user", text);
      messageInput.value = "";
      sendButton.disabled = true;
      setStatus("Running...");
      try {
        const data = await api("/api/chat", {
          method: "POST",
          body: JSON.stringify({
            user_id: userId.value,
            session_id: sessionId.value,
            message: text
          })
        });
        addBubble("assistant", data.answer);
        setStatus("Ready");
        await refreshState();
      } catch (error) {
        setStatus(error.message, true);
        addBubble("assistant", error.message);
      } finally {
        sendButton.disabled = false;
        messageInput.focus();
      }
    }

    document.getElementById("chatForm").addEventListener("submit", sendMessage);
    document.getElementById("refreshButton").addEventListener("click", () => refreshState().catch(err => setStatus(err.message, true)));
    refreshState().catch(err => setStatus(err.message, true));
  </script>
</body>
</html>
"""


class TraceWeaveHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], runtime: AgentRuntime, store: SQLiteStore):
        super().__init__(server_address, TraceWeaveRequestHandler)
        self.runtime = runtime
        self.store = store
        self.runtime_lock = threading.Lock()


class TraceWeaveRequestHandler(BaseHTTPRequestHandler):
    server: TraceWeaveHTTPServer

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - stdlib signature.
        return

    def do_GET(self) -> None:  # noqa: N802 - stdlib callback.
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html(HTML_PAGE)
            return
        if parsed.path == "/api/todos":
            try:
                query = parse_qs(parsed.query)
                user_id, session_id = self._ids_from_query(query)
                todos = self.server.store.list_todos(user_id, session_id)
                self._send_json(
                    {
                        "todos": [
                            {"id": todo.id, "title": todo.title, "status": todo.status}
                            for todo in todos
                        ]
                    }
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if parsed.path == "/api/traces":
            try:
                query = parse_qs(parsed.query)
                user_id, session_id = self._ids_from_query(query)
                traces = self.server.store.list_traces(user_id, session_id)
                self._send_json(
                    {
                        "traces": [
                            {
                                "id": trace.id,
                                "step_index": trace.step_index,
                                "event_type": trace.event_type,
                                "tool_name": trace.tool_name,
                                "status": trace.status,
                                "result_summary": trace.result_summary,
                            }
                            for trace in traces
                        ]
                    }
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802 - stdlib callback.
        parsed = urlparse(self.path)
        if parsed.path != "/api/chat":
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            payload = self._read_json()
            user_id = self._required_string(payload, "user_id")
            session_id = self._required_string(payload, "session_id")
            message = self._required_string(payload, "message")
            with self.server.runtime_lock:
                answer = self.server.runtime.run_turn(user_id, session_id, message)
            self._send_json({"answer": answer})
        except ValueError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # noqa: BLE001 - local UI boundary.
            self._send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def _read_json(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            raise ValueError("Missing JSON body")
        raw = self.rfile.read(length)
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON body must be an object")
        return data

    @staticmethod
    def _required_string(payload: dict[str, object], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Missing required field: {key}")
        return value.strip()

    def _ids_from_query(self, query: dict[str, list[str]]) -> tuple[str, str]:
        user_id = (query.get("user_id") or [""])[0].strip()
        session_id = (query.get("session_id") or [""])[0].strip()
        if not user_id or not session_id:
            raise ValueError("user_id and session_id are required")
        return user_id, session_id

    def _send_html(self, body: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def _send_json(self, payload: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)


def build_server(project_root: Path, host: str, port: int) -> TraceWeaveHTTPServer:
    runtime = build_runtime_from_env(project_root)
    return TraceWeaveHTTPServer((host, port), runtime, runtime.store)


def serve(project_root: Path, host: str = "127.0.0.1", port: int = 8787) -> None:
    try:
        server = build_server(project_root, host, port)
    except ConfigError:
        raise
    print(f"TraceWeave web UI: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
