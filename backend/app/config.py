from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    anthropic_auth_token: str
    anthropic_base_url: str
    anthropic_model: str
    data_dir: Path
    sandbox_dir: Path


def get_settings() -> Settings:
    data_dir = _BASE_DIR / "data"
    sandbox_dir = _BASE_DIR / "sandbox"
    data_dir.mkdir(exist_ok=True)
    sandbox_dir.mkdir(exist_ok=True)
    return Settings(
        anthropic_auth_token=os.getenv("ANTHROPIC_AUTH_TOKEN", ""),
        anthropic_base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
        data_dir=data_dir,
        sandbox_dir=sandbox_dir,
    )


settings = get_settings()
