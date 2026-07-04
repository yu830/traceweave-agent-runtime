"""Pydantic models for the LLM JSON Action Protocol."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class LLMAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["tool_call", "final_answer"]
    reasoning_summary: str = Field(min_length=1, max_length=1000)
    tool_call: ToolCall | None = None
    final_answer: str | None = None

    @model_validator(mode="after")
    def validate_action_shape(self) -> "LLMAction":
        if self.action == "tool_call":
            if self.tool_call is None:
                raise ValueError("tool_call action requires tool_call")
            if self.final_answer is not None:
                raise ValueError("tool_call action requires final_answer to be null")
        if self.action == "final_answer":
            if self.final_answer is None or self.final_answer == "":
                raise ValueError("final_answer action requires final_answer")
            if self.tool_call is not None:
                raise ValueError("final_answer action requires tool_call to be null")
        return self

