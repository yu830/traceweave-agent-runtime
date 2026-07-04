from __future__ import annotations

import os

import pytest

from traceweave_agent_runtime.config import RuntimeConfig
from traceweave_agent_runtime.llm.openai_compatible import OpenAICompatibleLLM
from traceweave_agent_runtime.runtime.parser import ActionParser


def test_real_llm_json_action_protocol_optional() -> None:
    if os.getenv("RUN_LLM_TESTS") != "1":
        pytest.skip("Set RUN_LLM_TESTS=1 to run real LLM integration tests.")
    required = ["OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        pytest.skip(f"Missing real LLM environment variables: {', '.join(missing)}")

    llm = OpenAICompatibleLLM(RuntimeConfig.from_env())
    raw = llm.complete(
        [
            {
                "role": "system",
                "content": (
                    "Return only a JSON object with action=final_answer, "
                    "reasoning_summary short, tool_call null, final_answer set to pong."
                ),
            },
            {"role": "user", "content": "ping"},
        ]
    )
    action = ActionParser().parse(raw)
    assert action.action == "final_answer"

