"""Command line: `python -m dubber.cli <youtube-url-or-file>`."""

from __future__ import annotations

import argparse
import sys

from . import languages, pipeline
from .config import load_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dub a video (any language) into Russian or another language.")
    parser.add_argument("source", help="YouTube URL or path to a local video file")
    parser.add_argument("--lang", choices=sorted(languages.LANGUAGES), help="dub language (default: ru)")
    parser.add_argument("--voice", help="male / female, or an edge-tts voice, e.g. ru-RU-SvetlanaNeural")
    parser.add_argument("--whisper-model", help="tiny / base / small / medium / large-v3")
    parser.add_argument("--translator", choices=["auto", "google", "claude"])
    args = parser.parse_args(argv)

    settings = load_settings()
    if args.lang:
        settings.target_lang = args.lang
    if args.voice:
        settings.voice = args.voice
    if args.whisper_model:
        settings.whisper_model = args.whisper_model
    if args.translator:
        settings.translator = args.translator

    def progress(label: str, fraction: float) -> None:
        print(f"\r[{fraction * 100:5.1f}%] {label}...".ljust(60), end="", flush=True)

    result = pipeline.run(args.source, settings, progress=progress)
    print(f"\nГотово: {result.title}\n  Видео:     {result.video}\n  Субтитры:  {result.dub_srt}")
    print(f"  Текст:     {result.transcript}\n  Оригинал + перевод: {result.bilingual}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
