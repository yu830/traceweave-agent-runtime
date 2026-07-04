"""Small JSON helpers used by logs, traces, and docs output."""

from __future__ import annotations

import json
from typing import Any


def to_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def to_pretty_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=True, sort_keys=True, indent=2)


def from_json_or_none(raw: str | None) -> Any:
    if not raw:
        return None
    return json.loads(raw)

