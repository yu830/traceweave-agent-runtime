from __future__ import annotations


def test_message_history_persisted(store) -> None:
    store.add_message("alice", "s1", "user", "hello")
    store.add_message("alice", "s1", "assistant", "hi")
    messages = store.list_messages("alice", "s1")
    assert [message.role for message in messages] == ["user", "assistant"]


def test_messages_and_traces_isolated_by_session(store) -> None:
    store.add_message("alice", "s1", "user", "session one")
    store.add_message("alice", "s2", "user", "session two")
    store.add_trace("run1", "alice", "s1", 1, "tool_result", "calculator", result_summary="s1")
    assert len(store.list_messages("alice", "s1")) == 1
    assert store.list_messages("alice", "s1")[0].content == "session one"
    assert store.list_traces("alice", "s2") == []

