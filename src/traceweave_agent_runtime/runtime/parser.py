"""Parser for provider-neutral JSON action responses."""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from traceweave_agent_runtime.runtime.actions import LLMAction
from traceweave_agent_runtime.runtime.errors import (
    LLMOutputParseError,
    LLMOutputValidationError,
)


class ActionParser:
    """Extract and validate the runtime action emitted by an LLM."""

    _fenced_json_re = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)

    def parse(self, raw_output: str) -> LLMAction:
        json_text = self._extract_json_text(raw_output)
        try:
            payload = json.loads(json_text)
        except json.JSONDecodeError as exc:
            raise LLMOutputParseError(f"Invalid JSON emitted by LLM: {exc}") from exc
        try:
            return LLMAction.model_validate(payload)
        except ValidationError as exc:
            raise LLMOutputValidationError(f"LLM action does not match protocol: {exc}") from exc
        except ValueError as exc:
            raise LLMOutputValidationError(f"LLM action does not match protocol: {exc}") from exc

    def _extract_json_text(self, raw_output: str) -> str:
        text = raw_output.strip()
        if not text:
            raise LLMOutputParseError("LLM output is empty")
        fenced = self._fenced_json_re.search(text)
        if fenced:
            return fenced.group(1).strip()
        if text.startswith("{") and text.endswith("}"):
            return text
        extracted = self._extract_balanced_object(text)
        if extracted:
            return extracted
        raise LLMOutputParseError("No JSON object found in LLM output")

    @staticmethod
    def _extract_balanced_object(text: str) -> str | None:
        start = text.find("{")
        if start < 0:
            return None
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]
        return None

