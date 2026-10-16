"""The Segment data model and helpers to (de)serialize and regroup segments."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

_SENTENCE_END = (".", "!", "?", "…", '."', '?"', '!"')


@dataclass
class Segment:
    start: float  # seconds
    end: float  # seconds
    text: str  # English
    ru: str = ""  # Russian translation

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


def save_segments(segments: list[Segment], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([asdict(s) for s in segments], ensure_ascii=False, indent=1), encoding="utf-8"
    )


def load_segments(path: Path) -> list[Segment]:
    return [Segment(**d) for d in json.loads(path.read_text(encoding="utf-8"))]


def merge_into_sentences(
    segments: list[Segment], max_duration: float = 12.0, max_gap: float = 0.6
) -> list[Segment]:
    """Join Whisper fragments that belong to one sentence.

    Translating whole sentences gives much better Russian, and longer slots give the Russian
    voice more room. A fragment is appended to the previous one when the previous one does not
    end a sentence, the pause between them is short, and the result stays under `max_duration`.
    """
    merged: list[Segment] = []
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        if merged:
            prev = merged[-1]
            if (
                not prev.text.rstrip().endswith(_SENTENCE_END)
                and seg.start - prev.end <= max_gap
                and seg.end - prev.start <= max_duration
            ):
                prev.text = f"{prev.text.rstrip()} {text}"
                prev.end = seg.end
                continue
        merged.append(Segment(start=seg.start, end=seg.end, text=text))
    return merged
