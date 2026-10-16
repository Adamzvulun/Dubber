"""The Segment data model and helpers to (de)serialize and regroup segments."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

_SENTENCE_END = (".", "!", "?", "…", '."', '?"', '!"', "。", "！", "？")
_NON_SPEECH = re.compile(r"\[[^\]]*\]|\([^)]*\)|[♪♫]")  # Whisper's "[Music]", "(applause)", "♪"


@dataclass
class Word:
    start: float  # seconds
    end: float  # seconds
    text: str  # as Whisper gives it, usually with a leading space


@dataclass
class Segment:
    start: float  # seconds
    end: float  # seconds
    text: str  # what was said (any language; usually English)
    ru: str = ""  # the translation in the dub language (named "ru" for compatibility: Russian is the default)
    words: list[Word] = field(default_factory=list)  # word timings from Whisper (not saved)

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


def save_segments(segments: list[Segment], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([{k: v for k, v in asdict(s).items() if k != "words"} for s in segments],
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
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


def split_into_units(
    words: list[Word], hard_pause: float = 1.2, max_duration: float = 10.0, min_part: float = 2.5
) -> list[Segment]:
    """Group Whisper words into dubbing units with speech-only start/end times.

    A unit is one sentence: Whisper's own segments are 30-second-window chunks that hold several sentences and can
    cut one in half, so the dub could not pause where the speaker pauses. A sentence is also cut at a long pause
    (`hard_pause`), and a sentence longer than `max_duration` is cut at its best internal break (biggest pause,
    preferring a comma) so each part stays at least `min_part` seconds long.
    """
    sentences: list[list[Word]] = []
    current: list[Word] = []
    for i, w in enumerate(words):
        if not any(ch.isalnum() for ch in _NON_SPEECH.sub("", w.text)):  # "♪", "[Music]", "—": not speech
            if current and w.text.strip().endswith(_SENTENCE_END):
                sentences.append(current)
                current = []
            continue
        current.append(w)
        next_start = words[i + 1].start if i + 1 < len(words) else None
        if w.text.strip().endswith(_SENTENCE_END) or (next_start is not None and next_start - w.end >= hard_pause):
            sentences.append(current)
            current = []
    if current:
        sentences.append(current)

    units: list[Segment] = []
    for sentence in sentences:
        for part in _split_long(sentence, max_duration, min_part):
            text = " ".join(_NON_SPEECH.sub(" ", "".join(w.text for w in part)).split())
            if any(ch.isalnum() for ch in text):  # nothing to translate or say otherwise
                units.append(Segment(start=part[0].start, end=part[-1].end, text=text))
    return units


def _split_long(words: list[Word], max_duration: float, min_part: float) -> list[list[Word]]:
    if words[-1].end - words[0].start <= max_duration:
        return [words]
    best, best_score = None, -1.0
    for i in range(1, len(words)):
        left, right = words[i - 1].end - words[0].start, words[-1].end - words[i].start
        if left < min_part or right < min_part:
            continue
        comma = words[i - 1].text.rstrip().endswith((",", ";", ":", "—"))
        score = (words[i].start - words[i - 1].end) + (0.3 if comma else 0.0)
        if score > best_score:
            best, best_score = i, score
    if best is None:
        return [words]
    return _split_long(words[:best], max_duration, min_part) + _split_long(words[best:], max_duration, min_part)
