from __future__ import annotations

from pathlib import Path

from traceweave_agent_runtime.store.sqlite_store import SQLiteStore


def main() -> None:
    store = SQLiteStore(Path(".traceweave/demo_session_isolation.sqlite3"))
    store.init_db()
    store.add_todo("alice", "weather", "bring umbrella")
    store.add_todo("alice", "weekly", "submit weekly report")
    print("alice/weather:", [todo.title for todo in store.list_todos("alice", "weather")])
    print("alice/weekly:", [todo.title for todo in store.list_todos("alice", "weekly")])


if __name__ == "__main__":
    main()

