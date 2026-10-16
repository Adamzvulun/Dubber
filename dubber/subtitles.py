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


def to_srt(segments: list[Segment], translated: bool = True) -> str:
    blocks = []
    n = 0
    for seg in segments:
        text = (seg.ru if translated else seg.text).strip()
        if not text:
            continue
        n += 1
        blocks.append(f"{n}\n{srt_timestamp(seg.start)} --> {srt_timestamp(seg.end)}\n{text}\n")
    return "\n".join(blocks)


def to_vtt(segments: list[Segment], translated: bool = True) -> str:
    """WebVTT (what browsers use for <track>)."""
    cues = []
    for seg in segments:
        text = (seg.ru if translated else seg.text).strip()
        if text:
            start, end = srt_timestamp(seg.start).replace(",", "."), srt_timestamp(seg.end).replace(",", ".")
            cues.append(f"{start} --> {end}\n{text}\n")
    return "WEBVTT\n\n" + "\n".join(cues)


def _clock(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def to_transcript(segments: list[Segment], title: str = "") -> str:
    """Transcript in the dub language, grouped into paragraphs of about a minute, with time marks."""
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


def to_bilingual(segments: list[Segment], title: str = "", source: str = "en", target: str = "ru") -> str:
    """Original line + translated line, for studying the original wording."""
    src, tgt = (source or "orig").upper(), target.upper()
    width = max(len(src), len(tgt))
    lines = [title, ""] if title else []
    for seg in segments:
        lines += [f"[{_clock(seg.start)}] {src.ljust(width)}: {seg.text.strip()}",
                  f"         {tgt.ljust(width)}: {seg.ru.strip()}", ""]
    return "\n".join(lines)


def file_names(target: str = "ru") -> dict[str, str]:
    """Output file names for a dub into `target` (the website reads them from meta.json "files")."""
    return {
        "dub_srt": f"subtitles_{target}.srt",
        "dub_vtt": f"subtitles_{target}.vtt",
        "src_srt": "subtitles_src.srt",
        "src_vtt": "subtitles_src.vtt",
        "transcript": f"transcript_{target}.txt",
        "bilingual": f"transcript_src_{target}.txt",
    }


def write_all(
    segments: list[Segment], out_dir: Path, title: str = "", target: str = "ru", source: str = ""
) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    content = {
        "dub_srt": to_srt(segments, translated=True),
        "dub_vtt": to_vtt(segments, translated=True),
        "src_srt": to_srt(segments, translated=False),
        "src_vtt": to_vtt(segments, translated=False),
        "transcript": to_transcript(segments, title),
        "bilingual": to_bilingual(segments, title, source, target),
    }
    paths = {key: out_dir / name for key, name in file_names(target).items()}
    for key, path in paths.items():
        path.write_text(content[key], encoding="utf-8")
    return paths
