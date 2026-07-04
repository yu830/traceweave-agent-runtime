"""LLM interface used by the self-built runtime."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseLLM(ABC):
    @abstractmethod
    def complete(self, messages: list[dict[str, str]]) -> str:
        """Return the raw assistant text for the given chat messages."""

