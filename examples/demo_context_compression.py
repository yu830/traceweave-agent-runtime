from __future__ import annotations

from pathlib import Path

from traceweave_agent_runtime.runtime.compression import DeterministicCompressor
from traceweave_agent_runtime.store.sqlite_store import SQLiteStore


def main() -> None:
    store = SQLiteStore(Path(".traceweave/demo_compression.sqlite3"))
    store.init_db()
    user_id = "alice"
    session_id = "long-chat"
    store.add_todo(user_id, session_id, "keep final handoff checklist")
    for index in range(15):
        store.add_message(user_id, session_id, "user", f"old message {index}")
    compressor = DeterministicCompressor(store, max_recent_messages=8)
    summary = compressor.compress_if_needed(user_id, session_id)
    print(summary.summary_text if summary else "No compression needed.")
    print("unsummarized messages:", store.count_messages(user_id, session_id))


if __name__ == "__main__":
    main()

