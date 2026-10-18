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


def save_env(path: Path, updates: dict[str, str | None]) -> None:
    """Set (or, with None, remove) KEY=VALUE lines in a .env file, keeping every other line; apply them now too.

    The website's settings are saved this way (e.g. the Claude API key), so they survive a restart. The file is
    git-ignored and stays on this computer.
    """
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    out, done = [], set()
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
        if key in updates:
            if updates[key] is not None and key not in done:
                out.append(f"{key}={updates[key]}")
            done.add(key)
        else:
            out.append(line)
    out += [f"{k}={v}" for k, v in updates.items() if v is not None and k not in done]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    for key, value in updates.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


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
    # "auto" = Claude when an API key is set, otherwise free Google Translate; "google" = free only; "offline"
    translator: str = field(default_factory=lambda: _env("DUBBER_TRANSLATOR", "auto"))
    claude_model: str = field(default_factory=lambda: _env("DUBBER_CLAUDE_MODEL", "claude-opus-5-5"))
    # Anthropic API key (paid, opt-in; entered in the website's settings and saved in .env). Never printed.
    claude_key: str = field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", ""), repr=False)
    # Where the website saves settings, and the user's glossary ("term = translation" per line, used by Claude)
    env_file: Path = field(default_factory=lambda: Path(_env("DUBBER_ENV_FILE", str(PROJECT_ROOT / ".env"))))
    glossary_file: Path = field(
        default_factory=lambda: Path(_env("DUBBER_GLOSSARY_FILE", str(PROJECT_ROOT / "glossary.txt")))
    )
    # Language of the dub (code from dubber/languages.py: ru, en, he, uk, es, fr, de, it, pt, ar, zh, ja)
    target_lang: str = field(default_factory=lambda: _env("DUBBER_LANG", "ru"))
    # Edge voice, or "male"/"female"; a voice that doesn't speak target_lang is replaced by that language's voice
    voice: str = field(default_factory=lambda: _env("DUBBER_VOICE", "ru-RU-DmitryNeural"))
    # Fastest the Russian voice may speak (1.6 = 60% faster than its natural speed); see dubber/timing.py
    max_speedup: float = field(default_factory=lambda: float(_env("DUBBER_MAX_SPEEDUP", "1.6")))
    # Volume of the original audio under the Russian voice (0 = mute, 1 = unchanged)
    original_volume: float = field(default_factory=lambda: float(_env("DUBBER_ORIGINAL_VOLUME", "0.15")))
    # Keep the original soundtrack quietly under the Russian voice (False = Russian voice only)
    keep_background: bool = field(
        default_factory=lambda: _env("DUBBER_KEEP_BACKGROUND", "1").lower() not in ("0", "false", "no")
    )
    # Remove the speaker's voice from that background, keep music and sounds (Demucs; slower: +minutes per video)
    remove_voice: bool = field(
        default_factory=lambda: _env("DUBBER_REMOVE_VOICE", "0").lower() in ("1", "true", "yes")
    )
    # Volume of that voice-free background under the dub (it is lowered further while the dub speaks)
    music_volume: float = field(default_factory=lambda: float(_env("DUBBER_MUSIC_VOLUME", "0.7")))
    # Max video height to download (keeps files small)
    max_height: int = field(default_factory=lambda: int(_env("DUBBER_MAX_HEIGHT", "720")))


    def glossary(self) -> str:
        try:
            return self.glossary_file.read_text(encoding="utf-8").strip()
        except OSError:
            return ""


def load_settings() -> Settings:
    _load_dotenv(PROJECT_ROOT / ".env")
    return Settings()
