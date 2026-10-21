"""Runtime settings read from the environment (and an optional ``.env`` file)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

from occasio.core.knowledge import DEFAULT_DATA_DIR

# Small, inexpensive model by default; override with OCCASIO_MODEL.
# Current model list: https://docs.claude.com/en/docs/about-claude/models
DEFAULT_MODEL = "claude-haiku-5-5"

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    if raw in _TRUE:
        return True
    if raw in _FALSE:
        return False
    raise ValueError(f"{name} must be true or false, got {raw!r}")


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str
    model: str
    ai_enabled: bool
    db_path: Path
    data_dir: Path

    @property
    def ai_available(self) -> bool:
        return self.ai_enabled and bool(self.anthropic_api_key)

    def __repr__(self) -> str:  # never print the key
        key = "set" if self.anthropic_api_key else "unset"
        return f"Settings(model={self.model!r}, ai_enabled={self.ai_enabled}, key={key})"


def load_settings() -> Settings:
    load_dotenv(override=False)
    model = os.getenv("OCCASIO_MODEL", "").strip() or DEFAULT_MODEL
    if len(model) > 100 or not all(c.isalnum() or c in "-._:@" for c in model):
        raise ValueError("OCCASIO_MODEL contains unexpected characters")
    return Settings(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
        model=model,
        ai_enabled=_bool("OCCASIO_AI_ENABLED", True),
        db_path=Path(os.getenv("OCCASIO_DB_PATH", "").strip() or "occasio.db"),
        data_dir=Path(os.getenv("OCCASIO_DATA_DIR", "").strip() or DEFAULT_DATA_DIR),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
