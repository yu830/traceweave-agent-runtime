# Demo Script

This script is for screen recording guidance only. No recording file is required
in the repository.

## 1. Initialize Project And Database

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
traceweave init-db
```

## 2. Run Tests

```bash
pytest
```

Point out that the real LLM integration test is skipped unless RUN_LLM_TESTS=1
and the three OpenAI-compatible variables are present.

## 3. Direct Answer Demo

Configure .env with OPENAI_API_KEY, OPENAI_BASE_URL, and OPENAI_MODEL, then run:

```bash
traceweave chat --user-id alice --session-id direct --message "Return a short project summary."
traceweave show-messages --user-id alice --session-id direct
```

## 4. Weather + Todo Demo

```bash
traceweave chat \
  --user-id alice \
  --session-id weather \
  --message "Check Singapore weather and remember a todo: bring an umbrella tomorrow."

traceweave list-todos --user-id alice --session-id weather
```

## 5. Session Isolation Demo

```bash
traceweave chat \
  --user-id alice \
  --session-id weekly \
  --message "Create a weekly report outline and remember: submit report Friday."

traceweave list-todos --user-id alice --session-id weather
traceweave list-todos --user-id alice --session-id weekly
python examples/demo_session_isolation.py
```

## 6. Context Compression Demo

```bash
python examples/demo_context_compression.py
traceweave compress --user-id alice --session-id weather
traceweave show-messages --user-id alice --session-id weather
```

## 7. Trace Log Demo

```bash
traceweave show-traces --user-id alice --session-id weather
```

Show llm_request, llm_response, tool_call, tool_result, parser_error if any, and
compression rows.

## 8. Optional Local Web UI Demo

The written test accepts terminal or web operation recordings. This web UI is a
thin local interface over the same self-built runtime loop.

```bash
traceweave serve --host 127.0.0.1 --port 8787
```

Open `http://127.0.0.1:8787`, send a weather-plus-todo message, and show the
Todos and Trace panels updating.

## 9. README / Docs

Open README.md, docs/design_notes.md, docs/architecture_answers.md, and this
demo script. Emphasize that .env is not committed and real search/LLM calls are
optional.

