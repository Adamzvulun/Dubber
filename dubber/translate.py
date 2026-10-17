"""Stage 3 — speech lines (any language, several per video) to the dub language (see languages.py).

How a video is translated (`Translator`):
1. Lines already in the dub language are kept as they are.
2. The rest goes to the primary engine in batches of ONE spoken language each (`Segment.lang` from Whisper): a mixed
   batch made Google detect one language and leave the French lines of an English video untranslated.
   - GoogleBackend (free, default): Google's JSON endpoint, patient retries on its robot check / rate limit.
   - ClaudeBackend (opt-in, ANTHROPIC_API_KEY): context-aware, concise lines for dubbing.
3. If the primary engine stays unavailable, the rest of the video uses NllbBackend: Meta's NLLB-200 (1.3B, int8,
   CTranslate2, ~1.4 GB, downloaded on first use), offline, any language pair. It replaced an English→Russian-only
   model that turned French into gibberish when Google refused.
4. Quality gate: a line whose "translation" is still the original (or not in the dub language's script) is re-sent
   on its own; if it still isn't translated, the job stops — untranslated text is never voiced.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from collections.abc import Callable
from typing import Protocol

from . import languages
from .segments import Segment

log = logging.getLogger(__name__)


class Backend(Protocol):
    name: str

    def translate_group(self, lines: list[str], source: str) -> list[str]:
        """Translate lines that are all in one spoken language (`source`, a Whisper code; "" = unknown)."""
        ...


class TranslatorUnavailable(RuntimeError):
    """The engine can't be reached or refuses (e.g. Google's robot check); another engine may take over."""


class UntranslatedError(RuntimeError):
    """Some lines could not be translated by any engine."""


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


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+|(?<=[.!?…][\"')\]»])\s+")


def split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in _SENTENCE_SPLIT.split(text.strip())]
    return [p for p in parts if p]


def looks_like_block_page(text: str) -> bool:
    head = text.lstrip()[:300].lower()
    return head.startswith(("<!doctype", "<html")) or "unusual traffic" in head


# ---------------------------------------------------------------- Google (free, default)

class GoogleBackend:
    """Google Translate's JSON endpoint (the one browser extensions use), free, no key.

    Google answers some requests with a robot check / HTTP 429, more often from busy networks: wait and retry
    (2+4+8+16+30 s) before giving up with TranslatorUnavailable.
    """

    name = "google"
    URL = "https://translate.googleapis.com/translate_a/single"
    WAITS = (2, 4, 8, 16, 30)
    MAX_CHARS = 1500  # GET request: the text travels URL-encoded

    def __init__(self, target: str = languages.DEFAULT, fetch: Callable[[str, str, str], str] | None = None,
                 sleep: Callable[[float], None] = time.sleep, waits: tuple[float, ...] = WAITS):
        self.target = languages.get(target)
        # (text, source, target) -> translated text, or (text, detected source); raises TranslatorUnavailable
        self._fetch = fetch or self._http
        self.detected = ""  # source language Google detected in the last request
        self._sleep = sleep
        self._waits = waits

    @classmethod
    def _http(cls, text: str, source: str, target: str) -> tuple[str, str]:
        import requests

        try:
            r = requests.get(
                cls.URL, params={"client": "gtx", "sl": source, "tl": target, "dt": "t", "q": text},
                headers={"User-Agent": "Mozilla/5.0"}, timeout=20, allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise TranslatorUnavailable(f"Google Translate unreachable: {exc}") from exc
        if r.status_code != 200 or looks_like_block_page(r.text):
            raise TranslatorUnavailable(f"Google Translate refused the request (HTTP {r.status_code}, robot check)")
        try:
            data = r.json()
            return "".join(part[0] for part in data[0] if part and part[0]), str(data[2] or "")
        except (ValueError, TypeError, IndexError) as exc:
            raise TranslatorUnavailable(f"Google Translate sent an unexpected answer: {r.text[:120]}") from exc

    def _request(self, text: str, source: str) -> str:
        for attempt, wait in enumerate((*self._waits, None)):
            try:
                answer = self._fetch(text, source, self.target.google)
                text_out, self.detected = answer if isinstance(answer, tuple) else (answer, "")
                return text_out
            except TranslatorUnavailable as exc:
                if wait is None:
                    raise
                log.info("Google refused (%s); retry %d in %ss", exc, attempt + 1, wait)
                self._sleep(wait)
        raise AssertionError("unreachable")

    def translate_group(self, lines: list[str], source: str = "") -> list[str]:
        src = languages.google_code(source)
        out: list[str] = []
        for chunk in _chunks(lines, max_chars=self.MAX_CHARS, max_items=40):
            joined = "\n".join(t.replace("\n", " ") for t in chunk)
            parts = [ln.strip() for ln in self._request(joined, src).split("\n")]
            if len(parts) != len(chunk):  # line structure got lost — one by one
                parts = [self._request(t, src).strip() for t in chunk]
            out.extend(parts)
        return out

    def translate_one(self, line: str, source: str) -> str:
        """Quality-gate retry for one line. Google auto-detects a single line reliably, which also covers a line
        whose spoken language was mis-detected. If Google says the line is already in the dub language, keep it."""
        out = self._request(line, "auto").strip()
        if self.detected.lower() in (self.target.google.lower(), self.target.code):
            self.detected = self.target.code
        return out


# ---------------------------------------------------------------- NLLB-200 (free, offline, any pair)

class NllbBackend:
    """Meta's NLLB-200 distilled 1.3B (CC-BY-NC 4.0 — fine for personal use), CTranslate2 int8 conversion by OpenNMT.

    Measured 2026-10-16 on CPU: ~1 s per line; good French/English → Russian/Hebrew/Spanish. Known weaknesses handled
    here: it may stop after the first sentence (→ translate sentence by sentence) and Chinese output may stop at a
    comma (→ stricter length penalty, then clause by clause).
    """

    name = "offline"
    REPO = "OpenNMT/nllb-200-distilled-1.3B-ct2-int8"

    def __init__(self, target: str = languages.DEFAULT):
        import ctranslate2
        from huggingface_hub import snapshot_download
        from tokenizers import Tokenizer

        from .hub import retry

        self.target = languages.get(target)
        path = retry(lambda: snapshot_download(self.REPO))
        self._tok = Tokenizer.from_file(os.path.join(path, "tokenizer.json"))
        self._model = ctranslate2.Translator(path, device="cpu", compute_type="int8")

    def _run(self, texts: list[str], src: str) -> list[str]:
        if not texts:
            return []
        tokens = [[src, *self._tok.encode(t, add_special_tokens=False).tokens, "</s>"] for t in texts]
        results = self._model.translate_batch(
            tokens, target_prefix=[[self.target.nllb]] * len(texts), beam_size=4, length_penalty=1.5,
            max_decoding_length=256,
        )
        texts = [self._tok.decode([self._tok.token_to_id(t) for t in r.hypotheses[0][1:]]).strip() for r in results]
        return [re.sub(r"\s+([.,!?;:…])", r"\1", t) for t in texts]  # NLLB sometimes leaves "word ."

    def _looks_cut(self, source: str, out: str) -> bool:
        return not out or out.endswith((",", "，", "、")) and not source.rstrip().endswith(",")

    def translate_group(self, lines: list[str], source: str = "") -> list[str]:
        src = languages.nllb_code(source)
        sentences = [split_sentences(line) for line in lines]
        flat = self._run([s for group in sentences for s in group], src)
        out, i = [], 0
        for group in sentences:
            parts = []
            for sentence in group:
                text = flat[i]
                i += 1
                if self._looks_cut(sentence, text):  # stopped early: translate clause by clause
                    clauses = [c for c in re.split(r"(?<=[,;:])\s+", sentence) if c]
                    joiner = "，" if self.target.code in ("zh", "ja") else " "
                    text = joiner.join(c.rstrip("，,") for c in self._run(clauses, src)) if len(clauses) > 1 else text
                parts.append(text)
            out.append((" " if self.target.code not in ("zh", "ja") else "").join(parts))
        return out

    def translate_one(self, line: str, source: str) -> str:
        return self.translate_group([line], source)[0]


# ---------------------------------------------------------------- quality gate + orchestration

def needs_retry(source: str, out: str, line_lang: str, target: languages.Language) -> bool:
    """True when `out` is not a translation of `source` into `target` (untranslated or wrong script)."""
    if not any(c.isalpha() for c in source):
        return False
    if not out.strip():
        return True
    if target.script and not re.search(f"[{target.script}]", out):
        return True  # e.g. French text came back for a Russian dub
    words = len(source.split())
    return line_lang != target.code and out.strip().casefold() == source.strip().casefold() and words >= 3


class Translator:
    """Translate a video's lines: same-language lines kept, one-language batches, fallback, quality gate."""

    def __init__(self, target: str, primary, fallback_factory: Callable[[], object] | None = None):
        self.target = languages.get(target)
        self.primary = primary
        self._fallback_factory = fallback_factory
        self._fallback = None
        self.primary_failed = False
        self.used: set[str] = set()

    @property
    def name(self) -> str:
        return "+".join(sorted(self.used)) or self.primary.name

    def _engine(self):
        if not self.primary_failed:
            return self.primary
        if self._fallback is None:
            if self._fallback_factory is None:
                raise TranslatorUnavailable(f"{self.primary.name} translator unavailable and no fallback")
            self._fallback = self._fallback_factory()
        return self._fallback

    def _call(self, method: str, *args):
        while True:
            engine = self._engine()
            try:
                result = getattr(engine, method)(*args)
                self.used.add(engine.name)
                return result
            except TranslatorUnavailable as exc:
                if engine is not self.primary:
                    raise
                log.warning("%s unavailable (%s); using the offline translator for the rest", engine.name, exc)
                self.primary_failed = True

    def translate_texts(self, texts: list[str], langs: list[str] | None = None) -> list[str]:
        langs = list(langs) if langs else [""] * len(texts)
        out: list[str | None] = [None] * len(texts)
        todo = []
        for i, (text, lang) in enumerate(zip(texts, langs, strict=True)):
            if lang == self.target.code or not any(c.isalpha() for c in text):
                out[i] = text  # already in the dub language (or nothing to translate)
            else:
                todo.append(i)
        # Consecutive lines of one spoken language form one batch.
        groups: list[list[int]] = []
        for i in todo:
            if groups and groups[-1][-1] == i - 1 and langs[groups[-1][-1]] == langs[i]:
                groups[-1].append(i)
            else:
                groups.append([i])
        for group in groups:
            result = self._call("translate_group", [texts[i] for i in group], langs[group[0]])
            for i, line in zip(group, result, strict=True):
                out[i] = line

        # Quality gate: re-send failures alone (explicit source language), then give up loudly.
        for i in todo:
            if needs_retry(texts[i], out[i] or "", langs[i], self.target):
                out[i] = self._call("translate_one", texts[i], langs[i])
                if getattr(self._engine(), "detected", "") == self.target.code:
                    langs[i] = self.target.code  # Google: this line is already in the dub language
                if needs_retry(texts[i], out[i] or "", langs[i], self.target) and self._fallback_factory:
                    self.primary_failed = True  # one more chance with the other engine
                    out[i] = self._call("translate_one", texts[i], langs[i])
        bad = [texts[i] for i in todo if needs_retry(texts[i], out[i] or "", langs[i], self.target)]
        if bad:
            raise UntranslatedError(f"Could not translate {len(bad)} line(s) into {self.target.name_en}: {bad[:3]}")
        return [line or "" for line in out]


# ---------------------------------------------------------------- Claude (opt-in, paid)

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


    def translate_group(self, lines: list[str], source: str = "") -> list[str]:
        return self.translate_texts(lines)

    def translate_one(self, line: str, source: str) -> str:
        return self.translate_texts([line])[0]


def make_backend(
    choice: str = "auto", claude_model: str = "claude-opus-5-5", glossary: str = "", target: str = languages.DEFAULT
) -> Translator:
    """The translator for a dub into `target`: auto = Claude if ANTHROPIC_API_KEY is set, else free Google; both fall
    back to the offline NLLB model. "offline" = NLLB only."""
    fallback = lambda: NllbBackend(target=target)  # noqa: E731 — built only if needed (1.4 GB model)
    if choice == "offline":
        return Translator(target, NllbBackend(target=target))
    if choice == "claude" or (choice == "auto" and os.environ.get("ANTHROPIC_API_KEY")):
        return Translator(target, ClaudeBackend(model=claude_model, glossary=glossary, target=target), fallback)
    return Translator(target, GoogleBackend(target=target), fallback)


def translate_segments(segments: list[Segment], backend) -> list[Segment]:
    """Fill `seg.ru` (the dub-language text). `backend` is a Translator, or any object with translate_texts()."""
    texts = [s.text for s in segments]
    if isinstance(backend, Translator):
        translated = backend.translate_texts(texts, [s.lang for s in segments])
    else:
        translated = backend.translate_texts(texts)
    if len(translated) != len(segments):
        raise RuntimeError(f"translator returned {len(translated)} lines for {len(segments)} segments")
    for seg, text in zip(segments, translated, strict=True):
        seg.ru = text
    return segments
