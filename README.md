# TraceWeave Agent Runtime

`traceweave-agent-runtime` is a minimal but complete Python Agent Runtime built
for an Agent engineering written-test submission. The Python package name is
`traceweave_agent_runtime`.

The runtime implements its own JSON action protocol, parser, tool registry,
context builder, deterministic compression, SQLite session store, trace logger,
and Typer CLI. It does not use LangGraph, LangChain Agent Executor, AutoGen,
CrewAI, OpenHands, OpenClaw, or LlamaIndex agent runtime for the main flow.

## Why Not Use Existing Agent Frameworks

The assignment is about runtime architecture. Using a framework would hide the
important engineering decisions: how model output is parsed, how tools are
registered and validated, how state is scoped, how context is compressed, and
how traces are persisted. TraceWeave keeps these responsibilities explicit and
testable.

## Features

- Provider-neutral JSON Action Protocol.
- OpenAI-compatible LLM adapter for GLM5.2-style endpoints.
- FakeLLM for deterministic tests.
- JSON Schema validated tools.
- SQLite sessions, messages, todos, summaries, notes, and traces.
- Session-scoped todo and note tools.
- Mock-first search and weather tools.
- Deterministic context compression.
- Typer CLI for chat, database setup, todos, messages, traces, and compression.
- pytest suite that does not require real API credentials by default.

## Architecture

```text
CLI / Tests / Examples
        |
        v
AgentRuntime.run_turn(user_id, session_id, user_input)
        |
        +--> SQLiteStore: sessions, messages, todos, summaries, traces
        +--> ContextBuilder: system policy, tool schemas, summary, todos, recent messages
        +--> LLM Adapter: OpenAI-compatible API or FakeLLM
        +--> ActionParser: JSON extraction and Pydantic validation
        +--> ToolRegistry: JSON Schema validation and handler execution
        +--> TraceLogger: llm_request, llm_response, tool_call, tool_result, errors
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

Python 3.11 or newer is required. This project was verified locally with
Python 3.13.9.

## Environment Variables

Create `.env` from the example:

```bash
cp .env.example .env
```

Required for real LLM usage:

```bash
OPENAI_API_KEY=...
OPENAI_BASE_URL=...
OPENAI_MODEL=...
```

Optional runtime settings:

```bash
TRACEWEAVE_DB_PATH=.traceweave/traceweave.sqlite3
SEARCH_PROVIDER=mock
SEARCH_API_KEY=
SEARCH_ENDPOINT=
SEARCH_TIMEOUT_SECONDS=5
```

Do not commit `.env`. The model name, base URL, and API key are not hard-coded
in the codebase.

## Running

Initialize the database:

```bash
traceweave init-db
```

Run one turn:

```bash
traceweave chat \
  --user-id alice \
  --session-id weather \
  --message "Check Singapore weather and remember a todo: bring an umbrella tomorrow."
```

List todos:

```bash
traceweave list-todos --user-id alice --session-id weather
```

Show messages:

```bash
traceweave show-messages --user-id alice --session-id weather
```

Show traces:

```bash
traceweave show-traces --user-id alice --session-id weather
```

Compress a session:

```bash
traceweave compress --user-id alice --session-id weather
```

## Tools

| Tool | Purpose | Notes |
| --- | --- | --- |
| calculator | Safe arithmetic | Uses AST whitelist, not eval |
| search | Search adapter | Defaults to mock; real search is optional |
| todo | Session-scoped tasks | add/list/complete/update |
| weather | Weather lookup | Deterministic mock by default |
| read_docs | Restricted doc reader | Only docs/ and examples/sample_docs/ |
| datetime | Current date/time | IANA timezone support |
| note | Session-scoped notes | add/list |

## Session Isolation

All persisted records include `user_id` and `session_id`. Store queries for
messages, todos, summaries, notes, and traces explicitly filter by both fields.
This means `alice/weather`, `alice/weekly`, and `bob/weather` are separate
state scopes even when they share the same SQLite database.

## Context And Memory

Each LLM request is built in this order:

1. System Prompt
2. Runtime Policy
3. Tool Schema Block
4. Relevant Memory Block
5. Session Summary Block
6. Open Todos Block
7. Recent Messages Block
8. Latest Tool Result Block
9. Current User Message

Full trace logs and full tool results do not enter context. The runtime passes
only the latest tool result summary to the next loop step. The memory block is a
placeholder in this minimal implementation; session summaries and structured
state provide the current continuity layer.

## Trace Logs

Trace rows are stored in `tool_traces` and can be viewed with:

```bash
traceweave show-traces --user-id alice --session-id weather
```

The runtime records `llm_request`, `llm_response`, `parser_error`, `tool_call`,
`tool_result`, `tool_error`, `max_steps_reached`, and `compression`.

## Testing

Run:

```bash
pytest
```

All default tests use FakeLLM and mock adapters. Real LLM integration is skipped
unless all of the following are true:

```bash
RUN_LLM_TESTS=1
OPENAI_API_KEY=...
OPENAI_BASE_URL=...
OPENAI_MODEL=...
```

Do not fake real API test results.

## Demo Scenarios

- Direct final answer with FakeLLM in tests.
- Weather plus todo with the CLI and configured OpenAI-compatible endpoint.
- Session isolation via `examples/demo_session_isolation.py`.
- Context compression via `examples/demo_context_compression.py`.
- Trace log review via `traceweave show-traces`.

See `docs/demo_script.md` for a recording walkthrough. Recording files are not
required and should not be committed.

## Known Limitations

- The search tool is mock-first; real search is a generic optional adapter.
- Weather is deterministic mock data, not a live API.
- Context compression is deterministic and conservative.
- Long-term semantic memory recall is not implemented beyond the placeholder
  memory block and session summaries.
- CLI chat requires configured OpenAI-compatible LLM environment variables.

