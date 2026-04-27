"""분석 provider 설정과 .env 로딩."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_PROVIDER = "gemini"
GEMINI_MODEL = "gemini-2.5-flash-lite"
CLAUDE_MODEL = "claude-sonnet-4-6"


def load_env() -> None:
    """프로젝트 루트의 .env 값을 환경변수에 반영."""
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def get_analysis_provider() -> str:
    """사용할 분석 provider 이름 반환."""
    load_env()
    return os.getenv("KBO_ANALYSIS_PROVIDER", DEFAULT_PROVIDER).strip().lower()
