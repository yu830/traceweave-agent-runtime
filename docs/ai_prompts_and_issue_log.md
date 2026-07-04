# AI Prompts And Issue Log

## Purpose

This file documents how AI assistance was used while building the project and
what manual engineering decisions shaped the final implementation.

## Development Principles

- AI was used as an implementation assistant, not as an unchecked authority.
- Runtime boundaries were manually selected: parser, registry, store, context,
  compression, tracing, and CLI.
- Existing Agent frameworks were not used for the main flow.
- Test results must come from actual pytest runs. Failed runs should be recorded
  as failures until they are fixed and rerun.

## Key Prompts

- Build a minimal Python Agent Runtime named traceweave-agent-runtime.
- Implement a provider-neutral JSON Action Protocol instead of native function
  calling.
- Persist sessions, messages, todos, summaries, and traces in SQLite with
  user_id plus session_id isolation.
- Add deterministic unit tests with FakeLLM and skip real LLM tests by default.

## Issue Log

- Risk: provider-specific function calling can differ across OpenAI-compatible
  endpoints.
  Fix: own the JSON protocol and parser locally.
- Risk: calculator security bug if eval is used.
  Fix: use Python ast parsing with explicit operator whitelisting.
- Risk: session data leakage.
  Fix: all store queries include user_id and session_id filters.
- Risk: flaky tests from real network services.
  Fix: default search to MockSearchAdapter and skip LLM tests unless explicitly
  enabled.

## Manual Architecture Decisions

- ToolRegistry owns validation and execution error capture.
- Full tool outputs stay in trace rows; context receives only result summaries.
- Compression is deterministic in the project implementation to keep tests
  reproducible.
- Todos and notes are structured state rather than inferred from chat history.

## Test Evidence

Local run after implementation:

```text
.........s..............                                                 [100%]
23 passed, 1 skipped in 0.11s
```

The skipped test is the real LLM integration test, which is intentionally gated
behind RUN_LLM_TESTS=1 and the required OpenAI-compatible environment variables.

## Remaining Limitations

- Memory recall is represented by a placeholder block; a real vector or hybrid
  memory index is out of scope for this minimal runtime.
- Real search is generic and optional. Production deployments should implement a
  provider-specific adapter with retries and result normalization.
- The compressor is deterministic and conservative rather than semantic.
