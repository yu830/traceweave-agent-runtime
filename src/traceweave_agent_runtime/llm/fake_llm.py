"""Deterministic LLM used by unit tests."""

from __future__ import annotations

from collections import deque

from traceweave_agent_runtime.llm.base import BaseLLM


class FakeLLM(BaseLLM):
    def __init__(self, responses: list[str] | tuple[str, ...]):
        self._responses = deque(responses)
        self.requests: list[list[dict[str, str]]] = []

    def complete(self, messages: list[dict[str, str]]) -> str:
        self.requests.append(messages)
        if not self._responses:
            return (
                '{"action":"final_answer","reasoning_summary":"No queued fake response.",'
                '"tool_call":null,"final_answer":"No fake response was configured."}'
            )
        return self._responses.popleft()

