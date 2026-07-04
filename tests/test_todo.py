from __future__ import annotations

from traceweave_agent_runtime.tools.todo import todo_handler


def test_todo_add_and_list(tool_context) -> None:
    added = todo_handler({"operation": "add", "title": "submit report"}, tool_context)
    assert "Added todo" in added.summary
    listed = todo_handler({"operation": "list"}, tool_context)
    assert listed.data["todos"][0]["title"] == "submit report"


def test_same_user_different_session_todo_isolation(store, tmp_path) -> None:
    from traceweave_agent_runtime.tools.base import ToolContext

    ctx_a = ToolContext("alice", "a", store, project_root=tmp_path)
    ctx_b = ToolContext("alice", "b", store, project_root=tmp_path)
    todo_handler({"operation": "add", "title": "session a task"}, ctx_a)
    assert todo_handler({"operation": "list"}, ctx_b).data["todos"] == []


def test_different_user_same_session_id_todo_isolation(store, tmp_path) -> None:
    from traceweave_agent_runtime.tools.base import ToolContext

    ctx_a = ToolContext("alice", "shared", store, project_root=tmp_path)
    ctx_b = ToolContext("bob", "shared", store, project_root=tmp_path)
    todo_handler({"operation": "add", "title": "alice-only task"}, ctx_a)
    assert todo_handler({"operation": "list"}, ctx_b).data["todos"] == []

