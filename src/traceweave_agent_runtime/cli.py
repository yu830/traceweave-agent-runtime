"""Command line interface for TraceWeave."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from traceweave_agent_runtime.config import RuntimeConfig
from traceweave_agent_runtime.runtime.agent_runtime import (
    build_default_tool_registry,
    build_runtime_from_env,
)
from traceweave_agent_runtime.runtime.compression import DeterministicCompressor
from traceweave_agent_runtime.runtime.errors import ConfigError
from traceweave_agent_runtime.store.sqlite_store import SQLiteStore
from traceweave_agent_runtime.web_app import serve as serve_web_app

app = typer.Typer(help="TraceWeave self-built agent runtime CLI.")
console = Console()


def _store(project_root: Path | None = None) -> SQLiteStore:
    config = RuntimeConfig.from_env(project_root or Path.cwd())
    store = SQLiteStore(config.db_path)
    store.init_db()
    return store


@app.command("init-db")
def init_db() -> None:
    """Create or migrate the SQLite database."""
    store = _store()
    console.print(f"Initialized database at [bold]{store.db_path}[/bold]")


@app.command("chat")
def chat(
    user_id: str = typer.Option(..., "--user-id"),
    session_id: str = typer.Option(..., "--session-id"),
    message: str = typer.Option(..., "--message"),
) -> None:
    """Run one agent turn with the configured OpenAI-compatible LLM."""
    try:
        runtime = build_runtime_from_env(Path.cwd())
    except ConfigError as exc:
        raise typer.BadParameter(str(exc)) from exc
    answer = runtime.run_turn(user_id, session_id, message)
    console.print(answer)


@app.command("list-todos")
def list_todos(
    user_id: str = typer.Option(..., "--user-id"),
    session_id: str = typer.Option(..., "--session-id"),
) -> None:
    """List todos for a user/session pair."""
    store = _store()
    todos = store.list_todos(user_id, session_id)
    table = Table(title=f"Todos for {user_id}/{session_id}")
    table.add_column("ID", justify="right")
    table.add_column("Status")
    table.add_column("Title")
    for todo in todos:
        table.add_row(str(todo.id), todo.status, todo.title)
    console.print(table)


@app.command("show-messages")
def show_messages(
    user_id: str = typer.Option(..., "--user-id"),
    session_id: str = typer.Option(..., "--session-id"),
) -> None:
    """Show persisted messages for a user/session pair."""
    store = _store()
    messages = store.list_messages(user_id, session_id, include_summarized=True)
    table = Table(title=f"Messages for {user_id}/{session_id}")
    table.add_column("ID", justify="right")
    table.add_column("Role")
    table.add_column("Summarized")
    table.add_column("Content")
    for message in messages:
        table.add_row(str(message.id), message.role, str(message.summarized), message.content[:120])
    console.print(table)


@app.command("show-traces")
def show_traces(
    user_id: str = typer.Option(..., "--user-id"),
    session_id: str = typer.Option(..., "--session-id"),
) -> None:
    """Show trace rows for a user/session pair."""
    store = _store()
    traces = store.list_traces(user_id, session_id)
    table = Table(title=f"Traces for {user_id}/{session_id}")
    table.add_column("ID", justify="right")
    table.add_column("Step", justify="right")
    table.add_column("Event")
    table.add_column("Tool")
    table.add_column("Status")
    table.add_column("Summary")
    for trace in traces:
        table.add_row(
            str(trace.id),
            str(trace.step_index),
            trace.event_type,
            trace.tool_name,
            trace.status,
            trace.result_summary[:120],
        )
    console.print(table)


@app.command("compress")
def compress(
    user_id: str = typer.Option(..., "--user-id"),
    session_id: str = typer.Option(..., "--session-id"),
) -> None:
    """Run deterministic context compression for a session."""
    config = RuntimeConfig.from_env(Path.cwd())
    store = _store()
    # Building the registry here keeps the command aligned with the normal runtime defaults.
    build_default_tool_registry()
    compressor = DeterministicCompressor(
        store,
        max_recent_messages=config.max_recent_messages,
        max_context_tokens=config.max_context_tokens,
        summary_target_tokens=config.summary_target_tokens,
    )
    summary = compressor.compress_if_needed(user_id, session_id)
    if summary is None:
        console.print("Compression not needed.")
    else:
        console.print(f"Created summary #{summary.id}: {summary.summary_text[:500]}")


@app.command("serve")
def serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8787, "--port"),
) -> None:
    """Run the local browser chat UI."""
    try:
        serve_web_app(Path.cwd(), host=host, port=port)
    except ConfigError as exc:
        raise typer.BadParameter(str(exc)) from exc


if __name__ == "__main__":
    app()

