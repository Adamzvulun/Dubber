"""Stage 3 — speech lines (any language) to the target language (Russian by default; see languages.py).

Backends share one interface (`translate_texts(list[str]) -> list[str]`):
- GoogleBackend: free, via deep-translator, source language auto-detected. Default.
- OfflineBackend: free, runs on this computer (Helsinki-NLP opus-mt-en-ru) — English→Russian only. Automatic
  fallback for Russian dubs when Google refuses (e.g. its "unusual traffic" robot check), or DUBBER_TRANSLATOR=offline.
- ClaudeBackend: context-aware, keeps lines short enough to dub. Used when ANTHROPIC_API_KEY is set.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from . import languages
from .segments import Segment

log = logging.getLogger(__name__)


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

    def __init__(self, translate_fn: Callable[[str], str] | None = None, target: str = languages.DEFAULT):
        if translate_fn is None:
            from deep_translator import GoogleTranslator

            translate_fn = GoogleTranslator(source="auto", target=languages.get(target).google).translate
        self._translate = translate_fn

    def translate_texts(self, texts: list[str]) -> list[str]:
        out: list[str] = []
        # Google's limit is 5000 chars per request; send many lines at once, one per line.
        for chunk in _chunks(texts, max_chars=4000, max_items=60):
            joined = "\n".join(t.replace("\n", " ") for t in chunk)
            lines = [ln.strip() for ln in self._checked(joined).split("\n")]
            if len(lines) != len(chunk):  # line structure got lost — fall back to one-by-one
                lines = [self._checked(t).strip() for t in chunk]
            # Google detects ONE source language per request, so in a mixed video (English with some French) a
            # line in the other language can come back untranslated. Re-send such lines on their own. When most
            # of the chunk is unchanged, the video is simply already in the target language: leave it.
            unchanged = [i for i, (src, dst) in enumerate(zip(chunk, lines, strict=True))
                         if dst.casefold() == src.strip().casefold() and any(c.isalpha() for c in src)]
            if unchanged and len(unchanged) <= len(chunk) // 2:
                for i in unchanged:
                    lines[i] = self._checked(chunk[i]).strip()
            out.extend(lines)
        return out

    def _checked(self, text: str) -> str:
        result = self._translate(text) or ""
        if looks_like_block_page(result):
            raise RuntimeError("Google Translate returned a robot-check page instead of a translation")
        return result


def looks_like_block_page(text: str) -> bool:
    head = text.lstrip()[:300].lower()
    return head.startswith(("<!doctype", "<html")) or "unusual traffic" in head


class OfflineBackend:
    """English→Russian on this computer: ONNX export of Helsinki-NLP/opus-mt-en-ru (Apache-2.0), ~110 MB.

    Lower quality than Google or Claude, but needs no account and works when online services refuse.
    The model downloads once from Hugging Face into the local cache.
    """

    name = "offline"
    REPO = "Xenova/opus-mt-en-ru"
    START_ID = 62517  # decoder_start_token_id (= pad) from the model's config.json
    EOS_ID = 0

    def __init__(self):
        import onnxruntime as ort
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer

        from .hub import retry

        def fetch(filename: str) -> str:
            return retry(lambda: hf_hub_download(self.REPO, filename))

        spec = json.loads(Path(fetch("tokenizer.json")).read_text(encoding="utf-8"))
        spec["normalizer"] = None  # the export has an empty "Precompiled" normalizer the library can't load
        self._tok = Tokenizer.from_str(json.dumps(spec))
        self._enc = ort.InferenceSession(fetch("onnx/encoder_model_quantized.onnx"))
        self._dec = ort.InferenceSession(fetch("onnx/decoder_model_quantized.onnx"))

    def _translate_one(self, text: str) -> str:
        import numpy as np

        if not text.strip():
            return ""
        ids = np.array([self._tok.encode(text).ids], dtype=np.int64)
        mask = np.ones_like(ids)
        hidden = self._enc.run(None, {"input_ids": ids, "attention_mask": mask})[0]
        out = [self.START_ID]
        for _ in range(3 * ids.shape[1] + 10):  # greedy decoding
            logits = self._dec.run(
                ["logits"],
                {"input_ids": np.array([out], dtype=np.int64), "encoder_hidden_states": hidden,
                 "encoder_attention_mask": mask},
            )[0]
            token = int(logits[0, -1].argmax())
            if token == self.EOS_ID:
                break
            out.append(token)
        return self._tok.decode(out[1:]).strip()

    def translate_texts(self, texts: list[str]) -> list[str]:
        # The model stops after the first sentence of its input, so translate sentence by sentence.
        return [" ".join(self._translate_one(s) for s in split_sentences(t)) for t in texts]


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+|(?<=[.!?…][\"')\]»])\s+")


def split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENTENCE_SPLIT.split(text.strip())]
    return [p for p in parts if p]


class FallbackBackend:
    """Use `primary`; if it fails once, switch to `fallback` for the rest of the run."""

    def __init__(self, primary: Backend, fallback_factory: Callable[[], Backend]):
        self.primary = primary
        self._fallback_factory = fallback_factory
        self.used: Backend = primary

    @property
    def name(self) -> str:
        return self.used.name

    def translate_texts(self, texts: list[str]) -> list[str]:
        if self.used is self.primary:
            try:
                return self.primary.translate_texts(texts)
            except Exception as exc:
                log.warning("%s translator failed (%s); switching to the offline translator", self.primary.name, exc)
                self.used = self._fallback_factory()
        return self.used.translate_texts(texts)


CLAUDE_SYSTEM_PROMPT = """You translate video subtitles into natural spoken {target} for a voice-over.
The source is usually English but may be any language, or several (translate every line into {target};
keep a line that is already in {target}).
The listener is a {target}-speaking professional learning from this video.
Rules:
- Return exactly one {target} line per input line, in the same order (same count).
- Each translated line will be spoken in the same time slot as the original one, so keep it concise:
  prefer short, natural wording over literal translation, but never drop meaning.
- Keep technical terms accurate; keep product names, code and acronyms as in the original.
- Use the surrounding lines as context, but translate each line on its own row."""


class ClaudeBackend:
    name = "claude"

    def __init__(
        self, model: str = "claude-opus-5-5", client=None, glossary: str = "", target: str = languages.DEFAULT
    ):
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        self._client = client
        self._model = model
        self._glossary = glossary
        self._target = languages.get(target).name_en

    def _translate_chunk(self, chunk: list[str]) -> list[str]:
        numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(chunk))
        system = CLAUDE_SYSTEM_PROMPT.format(target=self._target)
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


def make_backend(
    choice: str = "auto", claude_model: str = "claude-opus-5-5", glossary: str = "", target: str = languages.DEFAULT
) -> Backend:
    if choice == "claude" or (choice == "auto" and os.environ.get("ANTHROPIC_API_KEY")):
        return ClaudeBackend(model=claude_model, glossary=glossary, target=target)
    offline_ok = target == "ru"  # the offline model only knows English→Russian
    if choice == "offline":
        if not offline_ok:
            raise RuntimeError("The offline translator only translates into Russian")
        return OfflineBackend()
    if choice == "google" or not offline_ok:
        return GoogleBackend(target=target)
    return FallbackBackend(GoogleBackend(target=target), OfflineBackend)


def translate_segments(segments: list[Segment], backend: Backend) -> list[Segment]:
    russian = backend.translate_texts([s.text for s in segments])
    if len(russian) != len(segments):
        raise RuntimeError(f"translator returned {len(russian)} lines for {len(segments)} segments")
    for seg, ru in zip(segments, russian, strict=True):
        seg.ru = ru
    return segments
