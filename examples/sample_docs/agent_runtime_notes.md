# Agent Runtime Notes

TraceWeave uses a provider-neutral JSON Action Protocol instead of native
function calling. The runtime owns parsing, validation, tool dispatch, session
state, context compression, and trace logging.

Key design points:

- Tool calls are validated with JSON Schema before execution.
- Session state is scoped by user_id and session_id.
- Full tool results remain in trace logs; only summaries enter LLM context.
- Compression is deterministic in tests and does not require a real LLM.

