from __future__ import annotations

import pytest

from traceweave_agent_runtime.runtime.errors import ToolExecutionError
from traceweave_agent_runtime.tools.calculator import SafeCalculator


def test_calculator_normal_math() -> None:
    assert SafeCalculator().evaluate("2 + 3 * (4 - 1) ** 2") == 29


def test_calculator_rejects_dangerous_expression() -> None:
    with pytest.raises(ToolExecutionError):
        SafeCalculator().evaluate("__import__('os').system('echo nope')")

