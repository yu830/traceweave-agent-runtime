"""OpenAI-compatible chat-completions adapter."""

from __future__ import annotations

from openai import OpenAI

from traceweave_agent_runtime.config import RuntimeConfig
from traceweave_agent_runtime.llm.base import BaseLLM
from traceweave_agent_runtime.runtime.errors import LLMAPIError


class OpenAICompatibleLLM(BaseLLM):
    def __init__(self, config: RuntimeConfig):
        config.require_llm()
        self._model = config.openai_model or ""
        self._max_tokens = config.openai_max_tokens
        self._temperature = config.openai_temperature
        self._client = OpenAI(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
            timeout=config.openai_timeout_seconds,
        )

    def complete(self, messages: list[dict[str, str]]) -> str:
        try:
            request = {
                "model": self._model,
                "messages": messages,
                "temperature": self._temperature,
            }
            if self._max_tokens is not None:
                request["max_tokens"] = self._max_tokens
            response = self._client.chat.completions.create(**request)
        except Exception as exc:  # noqa: BLE001 - keep provider errors wrapped.
            raise LLMAPIError(f"LLM API call failed: {exc}") from exc
        content = response.choices[0].message.content
        if not content:
            raise LLMAPIError("LLM returned an empty response")
        return content

