from __future__ import annotations

import pytest

from traceweave_agent_runtime.runtime.errors import (
    LLMOutputParseError,
    LLMOutputValidationError,
)
from traceweave_agent_runtime.runtime.parser import ActionParser


def test_parser_parses_tool_call() -> None:
    action = ActionParser().parse(
        """```json
        {
          "action": "tool_call",
          "reasoning_summary": "Need calculation.",
          "tool_call": {"name": "calculator", "arguments": {"expression": "2+2"}},
          "final_answer": null
        }
        ```"""
    )
    assert action.action == "tool_call"
    assert action.tool_call is not None
    assert action.tool_call.name == "calculator"


def test_parser_parses_final_answer_with_text_around_json() -> None:
    action = ActionParser().parse(
        'Here is the action: {"action":"final_answer","reasoning_summary":"Done.",'
        '"tool_call":null,"final_answer":"hello"}'
    )
    assert action.action == "final_answer"
    assert action.final_answer == "hello"


def test_parser_rejects_invalid_json() -> None:
    with pytest.raises(LLMOutputParseError):
        ActionParser().parse('{"action": "final_answer",')


def test_parser_rejects_invalid_action() -> None:
    with pytest.raises(LLMOutputValidationError):
        ActionParser().parse(
            '{"action":"bad","reasoning_summary":"Nope.","tool_call":null,"final_answer":"x"}'
        )

