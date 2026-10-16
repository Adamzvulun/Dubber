"""Subtitle (.srt) and transcript (.txt) writers."""

from __future__ import annotations

from pathlib import Path

from .segments import Segment


def srt_timestamp(seconds: float) -> str:
    ms = max(0, round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(segments: list[Segment], russian: bool = True) -> str:
    blocks = []
    n = 0
    for seg in segments:
        text = (seg.ru if russian else seg.text).strip()
        if not text:
            continue
        n += 1
        blocks.append(f"{n}\n{srt_timestamp(seg.start)} --> {srt_timestamp(seg.end)}\n{text}\n")
    return "\n".join(blocks)


def _clock(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def to_transcript(segments: list[Segment], title: str = "") -> str:
    """Russian transcript, grouped into paragraphs of about a minute, with time marks."""
    lines = [title, ""] if title else []
    paragraph: list[str] = []
    para_start = segments[0].start if segments else 0.0
    for seg in segments:
        if paragraph and seg.start - para_start >= 60:
            lines += [f"[{_clock(para_start)}] " + " ".join(paragraph), ""]
            paragraph, para_start = [], seg.start
        if seg.ru.strip():
            paragraph.append(seg.ru.strip())
    if paragraph:
        lines += [f"[{_clock(para_start)}] " + " ".join(paragraph), ""]
    return "\n".join(lines)


def to_bilingual(segments: list[Segment], title: str = "") -> str:
    """English line + Russian line, for studying the original wording."""
    lines = [title, ""] if title else []
    for seg in segments:
        lines += [f"[{_clock(seg.start)}] EN: {seg.text.strip()}", f"         RU: {seg.ru.strip()}", ""]
    return "\n".join(lines)


def write_all(segments: list[Segment], out_dir: Path, title: str = "") -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "ru_srt": (out_dir / "subtitles_ru.srt", to_srt(segments, russian=True)),
        "en_srt": (out_dir / "subtitles_en.srt", to_srt(segments, russian=False)),
        "transcript": (out_dir / "transcript_ru.txt", to_transcript(segments, title)),
        "bilingual": (out_dir / "transcript_en_ru.txt", to_bilingual(segments, title)),
    }
    for path, content in files.values():
        path.write_text(content, encoding="utf-8")
    return {key: path for key, (path, _) in files.items()}
