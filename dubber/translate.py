"""Stage 3 — English segments to Russian.

Two backends behind one interface (`translate_texts(list[str]) -> list[str]`):
- GoogleBackend: free, via deep-translator. Default.
- ClaudeBackend: context-aware, keeps lines short enough to dub. Used when ANTHROPIC_API_KEY is set.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Protocol

from .segments import Segment


class Backend(Protocol):
    name: str

    def translate_texts(self, texts: list[str]) -> list[str]: ...


def _chunks(texts: list[str], max_chars: int, max_items: int) -> list[list[str]]:
    chunks: list[list[str]] = []
    current: list[str] = []
    size = 0
    for text in texts:
        if current and (size + len(text) + 1 > max_chars or len(current) >= max_items):
            chunks.append(current)
            current, size = [], 0
        current.append(text)
        size += len(text) + 1
    if current:
        chunks.append(current)
    return chunks


class GoogleBackend:
    name = "google"

    def __init__(self, translate_fn: Callable[[str], str] | None = None):
        if translate_fn is None:
            from deep_translator import GoogleTranslator

            translate_fn = GoogleTranslator(source="en", target="ru").translate
        self._translate = translate_fn

    def translate_texts(self, texts: list[str]) -> list[str]:
        out: list[str] = []
        # Google's limit is 5000 chars per request; send many lines at once, one per line.
        for chunk in _chunks(texts, max_chars=4000, max_items=60):
            joined = "\n".join(t.replace("\n", " ") for t in chunk)
            lines = [ln.strip() for ln in (self._translate(joined) or "").split("\n")]
            if len(lines) != len(chunk):  # line structure got lost — fall back to one-by-one
                lines = [(self._translate(t) or "").strip() for t in chunk]
            out.extend(lines)
        return out


CLAUDE_SYSTEM_PROMPT = """You translate English video subtitles into natural spoken Russian for a voice-over.
The listener is a Russian-speaking professional learning from this video.
Rules:
- Return exactly one Russian line per input line, in the same order (same count).
- Each Russian line will be spoken in the same time slot as the English one, so keep it concise:
  prefer short, natural wording over literal translation, but never drop meaning.
- Keep technical terms accurate; keep product names, code and acronyms as in the original.
- Use the surrounding lines as context, but translate each line on its own row."""


class ClaudeBackend:
    name = "claude"

    def __init__(self, model: str = "claude-opus-5-5", client=None, glossary: str = ""):
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        self._client = client
        self._model = model
        self._glossary = glossary

    def _translate_chunk(self, chunk: list[str]) -> list[str]:
        numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(chunk))
        system = CLAUDE_SYSTEM_PROMPT
        if self._glossary:
            system += f"\nGlossary (use these translations):\n{self._glossary}"
        response = self._client.beta.messages.create(
            model=self._model,
            max_tokens=16000,
            system=system,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={
                "effort": "low",
                "format": {
                    "type": "json_schema",
                    "schema": {
                        "type": "object",
                        "properties": {"translations": {"type": "array", "items": {"type": "string"}}},
                        "required": ["translations"],
                        "additionalProperties": False,
                    },
                },
            },
            messages=[{"role": "user", "content": f"Translate these {len(chunk)} lines:\n{numbered}"}],
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("Claude declined to translate this text")
        if response.stop_reason == "max_tokens":
            raise RuntimeError("Claude's translation was cut off (max_tokens)")
        text = next(b.text for b in response.content if b.type == "text")
        lines = [str(t).strip() for t in json.loads(text)["translations"]]
        if len(lines) != len(chunk):
            raise ValueError(f"expected {len(chunk)} translations, got {len(lines)}")
        return lines

    def translate_texts(self, texts: list[str]) -> list[str]:
        out: list[str] = []
        for chunk in _chunks(texts, max_chars=6000, max_items=80):
            try:
                out.extend(self._translate_chunk(chunk))
            except ValueError:
                # Count mismatch: retry in halves, which almost always lines up.
                half = max(1, len(chunk) // 2)
                for part in (chunk[:half], chunk[half:]):
                    if part:
                        out.extend(self._translate_chunk(part))
        return out


def make_backend(choice: str = "auto", claude_model: str = "claude-opus-5-5", glossary: str = "") -> Backend:
    if choice == "claude" or (choice == "auto" and os.environ.get("ANTHROPIC_API_KEY")):
        return ClaudeBackend(model=claude_model, glossary=glossary)
    return GoogleBackend()


def translate_segments(segments: list[Segment], backend: Backend) -> list[Segment]:
    russian = backend.translate_texts([s.text for s in segments])
    if len(russian) != len(segments):
        raise RuntimeError(f"translator returned {len(russian)} lines for {len(segments)} segments")
    for seg, ru in zip(segments, russian, strict=True):
        seg.ru = ru
    return segments
