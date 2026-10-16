"""Settings, read from environment variables (or a `.env` file in the project root)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader (KEY=VALUE lines) so users don't need extra packages."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default) or default


@dataclass
class Settings:
    work_dir: Path = field(default_factory=lambda: Path(_env("DUBBER_WORK_DIR", str(PROJECT_ROOT / "work"))))
    output_dir: Path = field(
        default_factory=lambda: Path(_env("DUBBER_OUTPUT_DIR", str(PROJECT_ROOT / "output")))
    )
    # faster-whisper model: tiny / base / small / medium / large-v3
    whisper_model: str = field(default_factory=lambda: _env("DUBBER_WHISPER_MODEL", "small"))
    whisper_device: str = field(default_factory=lambda: _env("DUBBER_DEVICE", "auto"))
    # "auto" = Claude when ANTHROPIC_API_KEY is set, otherwise free Google Translate
    translator: str = field(default_factory=lambda: _env("DUBBER_TRANSLATOR", "auto"))
    claude_model: str = field(default_factory=lambda: _env("DUBBER_CLAUDE_MODEL", "claude-opus-5-5"))
    voice: str = field(default_factory=lambda: _env("DUBBER_VOICE", "ru-RU-DmitryNeural"))
    # Fastest the Russian voice may speak (1.6 = 60% faster than its natural speed); see dubber/timing.py
    max_speedup: float = field(default_factory=lambda: float(_env("DUBBER_MAX_SPEEDUP", "1.6")))
    # Volume of the original audio under the Russian voice (0 = mute, 1 = unchanged)
    original_volume: float = field(default_factory=lambda: float(_env("DUBBER_ORIGINAL_VOLUME", "0.15")))
    # Keep the original soundtrack quietly under the Russian voice (False = Russian voice only)
    keep_background: bool = field(
        default_factory=lambda: _env("DUBBER_KEEP_BACKGROUND", "1").lower() not in ("0", "false", "no")
    )
    # Max video height to download (keeps files small)
    max_height: int = field(default_factory=lambda: int(_env("DUBBER_MAX_HEIGHT", "720")))


def load_settings() -> Settings:
    _load_dotenv(PROJECT_ROOT / ".env")
    return Settings()
