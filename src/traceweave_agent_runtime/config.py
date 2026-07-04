"""Environment-backed runtime configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from traceweave_agent_runtime.runtime.errors import ConfigError


@dataclass(frozen=True)
class RuntimeConfig:
    openai_api_key: str | None
    openai_base_url: str | None
    openai_model: str | None
    db_path: Path
    max_steps: int = 5
    max_recent_messages: int = 12
    max_context_tokens: int = 6000
    summary_target_tokens: int = 800

    @classmethod
    def from_env(cls, project_root: Path | None = None) -> "RuntimeConfig":
        load_dotenv()
        root = project_root or Path.cwd()
        db_path_raw = os.getenv("TRACEWEAVE_DB_PATH", ".traceweave/traceweave.sqlite3")
        db_path = Path(db_path_raw)
        if not db_path.is_absolute():
            db_path = root / db_path
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            openai_base_url=os.getenv("OPENAI_BASE_URL") or None,
            openai_model=os.getenv("OPENAI_MODEL") or None,
            db_path=db_path,
            max_steps=int(os.getenv("TRACEWEAVE_MAX_STEPS", "5")),
            max_recent_messages=int(os.getenv("TRACEWEAVE_MAX_RECENT_MESSAGES", "12")),
            max_context_tokens=int(os.getenv("TRACEWEAVE_MAX_CONTEXT_TOKENS", "6000")),
            summary_target_tokens=int(os.getenv("TRACEWEAVE_SUMMARY_TARGET_TOKENS", "800")),
        )

    def require_llm(self) -> None:
        missing = [
            name
            for name, value in {
                "OPENAI_API_KEY": self.openai_api_key,
                "OPENAI_BASE_URL": self.openai_base_url,
                "OPENAI_MODEL": self.openai_model,
            }.items()
            if not value
        ]
        if missing:
            raise ConfigError(
                "Missing LLM configuration: "
                + ", ".join(missing)
                + ". Set them in the environment or .env file."
            )

