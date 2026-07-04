# Design Notes

TraceWeave is intentionally small but has the same boundaries a larger runtime
needs: model adapter, parser, runtime loop, tool registry, session store,
context builder, compressor, and trace logger.

## Why JSON Action Protocol

OpenAI-compatible providers do not expose identical function-calling behavior.
The project therefore treats the model as a text generator and validates its
JSON action output locally. This makes the core loop provider neutral and easier
to test with FakeLLM.

## Runtime State

All persistent records include user_id and session_id. Session state is not held
in Python globals. This makes CLI demos repeatable and keeps tests from relying
on process-local state.

## Tool Safety

Tools are declared with JSON Schema and are executed through ToolRegistry.
Calculator uses an AST whitelist rather than eval. read_docs rejects absolute
paths and parent-directory traversal.

## Context Compression

The current compressor is deterministic. It preserves recent turns, writes a
structured summary for old messages, marks old messages summarized, and keeps
structured state such as open todos outside the free-text summary.

