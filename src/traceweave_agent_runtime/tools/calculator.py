"""Safe calculator tool implemented with an AST whitelist."""

from __future__ import annotations

import ast
import operator
from typing import Any

from traceweave_agent_runtime.runtime.errors import ToolExecutionError
from traceweave_agent_runtime.tools.base import ToolContext, ToolDefinition, ToolResult


CALCULATOR_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "expression": {"type": "string"},
    },
    "required": ["expression"],
    "additionalProperties": False,
}


class SafeCalculator:
    _bin_ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    _unary_ops = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }

    def evaluate(self, expression: str) -> int | float:
        if len(expression) > 256:
            raise ToolExecutionError("Expression is too long")
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise ToolExecutionError(f"Invalid mathematical expression: {exc.msg}") from exc
        return self._eval(tree.body)

    def _eval(self, node: ast.AST) -> int | float:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in self._bin_ops:
            left = self._eval(node.left)
            right = self._eval(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 12:
                raise ToolExecutionError("Exponent is too large")
            result = self._bin_ops[type(node.op)](left, right)
            if abs(float(result)) > 1e12:
                raise ToolExecutionError("Result magnitude is too large")
            return result
        if isinstance(node, ast.UnaryOp) and type(node.op) in self._unary_ops:
            return self._unary_ops[type(node.op)](self._eval(node.operand))
        raise ToolExecutionError("Expression contains unsupported or unsafe syntax")


def calculator_handler(arguments: dict[str, Any], context: ToolContext) -> ToolResult:
    del context
    expression = arguments["expression"]
    result = SafeCalculator().evaluate(expression)
    return ToolResult(
        data={"expression": expression, "result": result},
        summary=f"{expression} = {result}",
    )


def build_calculator_tool() -> ToolDefinition:
    return ToolDefinition(
        name="calculator",
        description="Safely evaluate arithmetic expressions using +, -, *, /, %, **, and parentheses.",
        parameters_schema=CALCULATOR_SCHEMA,
        handler=calculator_handler,
        is_read_only=True,
        timeout_seconds=3,
    )

