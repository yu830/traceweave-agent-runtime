"""Deterministic token estimate helpers.

This intentionally does not depend on provider-specific tokenizers. The runtime
only needs a conservative signal for compression thresholds.
"""

from __future__ import annotations


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def estimate_messages_tokens(messages: list[dict[str, str]]) -> int:
    return sum(estimate_tokens(message.get("content", "")) + 4 for message in messages)

