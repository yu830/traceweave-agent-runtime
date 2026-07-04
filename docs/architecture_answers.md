# Architecture Answers

## Module 1, Question 2: 200-Round Session Context Compression

### Problem Essence

A long session cannot keep sending every turn to the model. The runtime must
preserve task continuity while reducing token volume and avoiding irreversible
loss of structured state.

### Engineering Plan

Use layered context: latest turns, structured state, and compressed summaries.
Keep the last N messages verbatim, summarize older messages, and store durable
state such as todos separately from the free-text summary.

### Data Structures

- messages: raw user and assistant turns, with summarized flag.
- summaries: summary_text, start_message_id, end_message_id, reason.
- todos: structured pending work.
- tool_traces: full tool result history outside prompt context.

### Execution Flow

1. Save the new message.
2. Estimate context size and message count.
3. If thresholds are exceeded, summarize old unsummarized messages.
4. Mark those messages summarized.
5. Build future context from summary, open todos, recent messages, and latest
   tool result summary.

### Risks And Tradeoffs

Summaries can drop nuance. The mitigation is to keep recent messages verbatim
and keep operational state in tables. Full traces remain available for audit
but are not injected into every prompt.

### Project Mapping

Implemented in `runtime/compression.py` and `runtime/context_builder.py`.

## Module 2, Question 1: Memory Recall After Half A Month

### Problem Essence

The user expects the agent to remember a prior topic, but blindly injecting all
history is expensive and can surface irrelevant or stale facts.

### Engineering Plan

Use hybrid recall: structured memory for stable facts, semantic search for old
conversation summaries, and freshness checks for time-sensitive facts.

### Data Structures

- memory_items: user_id, namespace, text, embedding, confidence, last_seen.
- summaries: session-level compressed history.
- citations: source session and message id for retrieved facts.

### Execution Flow

1. Classify the current request as recall-sensitive.
2. Retrieve candidate memories by user_id and semantic similarity.
3. Filter by recency, confidence, and topic match.
4. Inject only concise memory snippets with provenance.
5. If stale, tell the user that the recalled fact may need verification.

### Risks And Tradeoffs

Over-recall can feel invasive or wrong. Under-recall makes the agent look
stateless. Provenance and confidence thresholds are important.

### Project Mapping

The current project has a Relevant Memory Block placeholder and summary support.
A production extension would add a memories table and retriever before context
construction.

## Module 3, Question 2: Daily 9 AM Review Task

### Problem Essence

Scheduled work is not a chat turn. It needs durable jobs, idempotency, and
clear rules for what session data is summarized.

### Engineering Plan

Create a scheduler-owned job that runs at 9 AM in the user's timezone, reads
yesterday's sessions, generates a review summary, stores it, and optionally
notifies the user.

### Data Structures

- scheduled_jobs: user_id, cron, timezone, status, last_run_at.
- job_runs: job_id, run_date, status, output_summary, error.
- summaries: generated review text linked to source sessions.

### Execution Flow

1. Scheduler claims due jobs with a lease.
2. Runtime gathers yesterday's messages and tool summaries.
3. Compressor/reviewer generates a daily recap.
4. Store the result and mark job_run success.
5. Notify the user or place the recap into the next session context.

### Risks And Tradeoffs

Duplicate jobs can create repeated summaries. Use idempotency keys such as
user_id plus local date. Time zones and daylight saving changes must be explicit.

### Project Mapping

TraceWeave already has summaries, messages, traces, and deterministic
compression. A scheduler would call those components outside `run_turn`.

## Module 4, Question 2: Busy Session With New User Message Or Tool Event

### Problem Essence

Concurrent events can corrupt state or produce out-of-order responses if the
runtime treats a session as always idle.

### Engineering Plan

Use a session state machine and event queue. When state is busy, new user input
and async tool completions become ordered events rather than immediate nested
runtime invocations.

### Data Structures

- sessions.status: idle, busy, waiting_tool, failed.
- event_queue: user_id, session_id, event_type, payload, sequence, status.
- tool_traces: async tool call and completion records.

### Execution Flow

1. Acquire a session lease before running a turn.
2. If busy, enqueue the incoming event.
3. Complete the active step and commit traces/messages.
4. Drain queued events in sequence.
5. Release lease or transition to waiting_tool.

### Risks And Tradeoffs

Strict ordering is safer but slower. Parallel tool work can improve latency but
needs correlation ids and careful merge rules.

### Project Mapping

This minimal project stores sessions.status but runs synchronously. Tool traces
and session rows are ready for a future queue/lease layer.

## Module 5, Question 1: Claude Code Tool Output vs OpenAI-Compatible Function Calling

### Problem Essence

Agent runtimes differ in whether tool calls are an application-level protocol or
a model/provider-native API feature.

### Engineering Plan

Claude Code style tools are orchestrated by the host runtime: the assistant asks
for a tool action, the host executes it, and tool output is returned as a
separate event. OpenAI-compatible function calling pushes tool-call structure
into the model API response and often requires provider-specific schema support.

### Data Structures

- Host-orchestrated tools: internal tool call events, trace rows, command
  outputs, approval state.
- Provider function calling: tool schema sent to API, function_call/tool_calls
  fields returned by the provider.

### Execution Flow

Host-orchestrated flow:
1. Model emits an action.
2. Runtime validates it.
3. Host executes the tool.
4. Runtime feeds summarized output back.

Provider-native flow:
1. Client sends schemas to the provider.
2. Provider returns structured tool call fields.
3. Client executes tools and sends tool responses back to provider.

### Risks And Tradeoffs

Host orchestration is portable and auditable but requires robust parsing.
Provider-native function calling can be cleaner and more constrained but varies
by provider and can make cross-provider behavior inconsistent.

### Project Mapping

TraceWeave uses a host-owned JSON Action Protocol so the same runtime can work
with NVIDIA GLM5.2 or another OpenAI-compatible endpoint without relying on
native function calling.

