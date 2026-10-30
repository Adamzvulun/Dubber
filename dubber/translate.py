"""Stage 3 — speech lines (any language, several per video) to the dub language (see languages.py).

How a video is translated (`Translator`):
1. Lines already in the dub language are kept as they are.
2. The rest goes to the primary engine in batches of ONE spoken language each (`Segment.lang` from Whisper): a mixed
   batch made Google detect one language and leave the French lines of an English video untranslated.
   - GoogleBackend (free, default): Google's JSON endpoint, patient retries on its robot check / rate limit.
   - ClaudeBackend (opt-in, paid; key entered in the website's settings): gets the WHOLE video instead — every line
     with its language, time slot and a character budget — so its lines fit the dub; follows the user's glossary.
3. If an engine stays unavailable, the next one takes over (Claude → Google → NLLB). Last in line is NllbBackend:
   Meta's NLLB-200 (1.3B, int8, CTranslate2, ~1.4 GB, downloaded on first use), offline, any language pair. It
   replaced an English→Russian-only model that turned French into gibberish when Google refused.
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
from dataclasses import dataclass
from typing import Protocol

from . import languages
from .segments import Segment
from .timing import slots

log = logging.getLogger(__name__)


class Backend(Protocol):
    name: str

    def translate_group(self, lines: list[str], source: str) -> list[str]:
        """Translate lines that are all in one spoken language (`source`, a Whisper code; "" = unknown)."""
        ...


class TranslatorUnavailable(RuntimeError):
    """The engine can't be reached or refuses (e.g. Google's robot check); another engine may take over.

    `code` says why, for the watch page: auth / permission / credit / unavailable / refusal ("" = not given).
    """

    def __init__(self, message: str = "", code: str = ""):
        super().__init__(message)
        self.code = code


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

    def _decode(self, tokens: list[str]) -> str:
        text = self._tok.decode([self._tok.token_to_id(t) for t in tokens]).strip()
        return re.sub(r"\s+([.,!?;:…])", r"\1", text)  # NLLB sometimes leaves "word ."

    def _generate(self, texts: list[str], src: str, prefixes=None, min_length: int = 0) -> list[list[str]]:
        tokens = [[src, *self._tok.encode(t, add_special_tokens=False).tokens, "</s>"] for t in texts]
        results = self._model.translate_batch(
            tokens, target_prefix=prefixes or [[self.target.nllb]] * len(texts), beam_size=4, length_penalty=1.5,
            min_decoding_length=min_length, max_decoding_length=256,
        )
        return [r.hypotheses[0][1:] for r in results]  # without the language token

    def _run(self, texts: list[str], src: str) -> list[str]:
        if not texts:
            return []
        out = []
        for text, hyp in zip(texts, self._generate(texts, src), strict=True):
            translated = self._decode(hyp)
            if self._looks_cut(text, translated):
                # Stopped after the first clause (seen for Chinese): make the model continue past the comma.
                more = self._generate([text], src, [[self.target.nllb, *hyp]], min_length=len(hyp) + 7)[0]
                if len(more) > len(hyp):
                    translated = self._decode(more)
            out.append(translated)
        return out

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
                if self._looks_cut(sentence, text):  # still stopped early: translate clause by clause
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
    """Translate a video's lines: same-language lines kept, fallback chain, quality gate.

    `fallbacks` are factories for the engines to use, in order, when the current one becomes unavailable (e.g.
    Claude → Google → offline NLLB); each is built only if needed. An engine with `translate_video` (Claude) gets the
    whole video at once with each line's language and time slot; the others get one-language batches.
    """

    def __init__(self, target: str, primary, fallbacks: Callable[[], object] | list[Callable[[], object]] = ()):
        self.target = languages.get(target)
        self.primary = primary
        self._factories = [fallbacks] if callable(fallbacks) else list(fallbacks)
        self._engines = [primary]
        self.used: set[str] = set()
        self.notes: list[str] = []  # why an engine was given up, e.g. "claude:credit" (shown on the watch page)

    @property
    def name(self) -> str:
        return "+".join(sorted(self.used)) or self.primary.name

    @property
    def cost_usd(self) -> float:
        return round(sum(getattr(e, "cost_usd", 0.0) for e in self._engines), 4)

    def _engine(self):
        return self._engines[-1]

    def _advance(self) -> bool:
        """Switch to the next engine for the rest of the video; False when there is none."""
        level = len(self._engines) - 1
        if level >= len(self._factories):
            return False
        self._engines.append(self._factories[level]())
        return True

    def _call(self, fn: Callable[[object], object]):
        while True:
            engine = self._engine()
            try:
                result = fn(engine)
                self.used.add(engine.name)
                return result
            except TranslatorUnavailable as exc:
                self.notes.append(f"{engine.name}:{exc.code}" if exc.code else engine.name)
                if not self._advance():
                    raise
                log.warning("%s unavailable (%s); using %s for the rest", engine.name, exc, self._engine().name)

    def _translate(self, engine, texts: list[str], langs: list[str], seconds: list[float | None], todo: list[int]):
        if hasattr(engine, "translate_video"):
            lines = [{"text": texts[i], "lang": langs[i], "seconds": seconds[i]} for i in todo]
            return dict(zip(todo, engine.translate_video(lines), strict=True))
        # Consecutive lines of one spoken language form one batch.
        groups: list[list[int]] = []
        for i in todo:
            if groups and groups[-1][-1] == i - 1 and langs[groups[-1][-1]] == langs[i]:
                groups[-1].append(i)
            else:
                groups.append([i])
        out: dict[int, str] = {}
        for group in groups:
            result = engine.translate_group([texts[i] for i in group], langs[group[0]])
            out.update(zip(group, result, strict=True))
        return out

    def translate_texts(
        self, texts: list[str], langs: list[str] | None = None, seconds: list[float | None] | None = None
    ) -> list[str]:
        """`langs`: spoken language per line; `seconds`: time slot per line (lets Claude fit the dub to it)."""
        langs = list(langs) if langs else [""] * len(texts)
        seconds = list(seconds) if seconds else [None] * len(texts)
        out: list[str | None] = [None] * len(texts)
        todo = []
        for i, (text, lang) in enumerate(zip(texts, langs, strict=True)):
            if lang == self.target.code or not any(c.isalpha() for c in text):
                out[i] = text  # already in the dub language (or nothing to translate)
            else:
                todo.append(i)
        if todo:
            # Engines are tried in order; a switch redoes the whole video with the next one (one consistent voice).
            for i, line in self._call(lambda e: self._translate(e, texts, langs, seconds, todo)).items():
                out[i] = line

        # Quality gate: re-send failures alone (explicit source language), then give up loudly.
        for i in todo:
            if needs_retry(texts[i], out[i] or "", langs[i], self.target):
                out[i] = self._call(lambda e, i=i: e.translate_one(texts[i], langs[i]))
                if getattr(self._engine(), "detected", "") == self.target.code:
                    langs[i] = self.target.code  # Google: this line is already in the dub language
                if needs_retry(texts[i], out[i] or "", langs[i], self.target) and self._advance():
                    out[i] = self._call(lambda e, i=i: e.translate_one(texts[i], langs[i]))  # one more engine
        bad = [texts[i] for i in todo if needs_retry(texts[i], out[i] or "", langs[i], self.target)]
        if bad:
            raise UntranslatedError(f"Could not translate {len(bad)} line(s) into {self.target.name_en}: {bad[:3]}")
        return [line or "" for line in out]


# ---------------------------------------------------------------- Claude (opt-in, paid)

@dataclass(frozen=True)
class ClaudeModel:
    label: str
    input_usd: float  # per million input tokens
    output_usd: float  # per million output tokens (thinking included)
    fallbacks: bool = True  # supports the server-side refusal fallback


# Anthropic API prices, 2026-10 (docs: platform.claude.com pricing). Opus 5.5 is the default.
CLAUDE_MODELS = {
    "claude-opus-5-5": ClaudeModel("Opus 5.5", 4.0, 20.0),
    "claude-sonnet-5-5": ClaudeModel("Sonnet 5.5", 2.0, 10.0),
    "claude-haiku-5-5": ClaudeModel("Haiku 5.5", 0.10, 0.50, fallbacks=False),
}
DEFAULT_CLAUDE_MODEL = "claude-opus-5-5"

# Part of the Claude cache key (pipeline.py): changing the prompt or the request translates cached videos again.
CLAUDE_PROMPT_VERSION = 3
CLAUDE_SYSTEM_PROMPT = """You translate the speech of a video into natural spoken {target} for a voice-over.
The speech may be in any language, or several (each line says its language); translate every line into {target}.
The listener is a {target}-speaking professional learning from this video. "video" gives its title and channel: use
them to understand the topic and its terms.
Rules:
- Return exactly one {target} line per input line, in the same order (same count).
- The text comes from automatic speech recognition: it can contain misheard words, missing punctuation or a wrong
  language label. When a word makes no sense in context, translate what the speaker most likely said.
- A line can be just part of a sentence that continues on the next line. Translate so that consecutive lines read as
  one natural {target} sentence, but keep each line's content on its own row.
- Each line is spoken in the time the speaker took ("seconds"). Aim for about "max_chars" characters: prefer short,
  natural spoken wording over a literal translation. Meaning comes first: never drop or change what is said to fit;
  a little over the budget is fine.
- Keep technical terms accurate and consistent through the whole video.
- A {target} voice reads your text aloud, and it says anything in another alphabet with a foreign accent. So write
  every word in the {target} writing system, as a {target} speaker would say it: names, product names and acronyms
  by their established {target} form or spelled as pronounced. Translate everything else; never leave a word in the
  original language or alphabet.
- "context_before" holds earlier lines of the same video, for context only: do not translate them."""

# Spelling that a speech engine needs (it reads exactly what is written), added to the prompt for that dub language.
SPEECH_NOTES = {
    "he": "Write standard Hebrew spelling (ktiv male as the Academy of the Hebrew Language defines it), without "
          "niqqud. A speech engine reads it aloud exactly as written, so an extra yod or vav changes the word: "
          "\"ייתר\" is read \"yiter\", the word for \"the rest\" is \"יתר\" (yeter).",
    "ru": "Write \"ё\" wherever it is pronounced (всё, её, ещё): a speech engine reads \"е\" otherwise. Names and "
          "acronyms in Russian letters, e.g. FBI -> ФБР, Kay -> Кей, iPhone -> айфон.",
}


class ClaudeBackend:
    """Claude via the Anthropic API (paid, opt-in with a key). Sees the whole video: every line with its language,
    its time slot and a character budget, so lines come out in dub length; follows the user's glossary."""

    name = "claude"
    MAX_LINES = 200  # lines per request (with the previous lines as context)
    CONTEXT_LINES = 12

    def __init__(
        self, model: str = DEFAULT_CLAUDE_MODEL, client=None, glossary: str = "", target: str = languages.DEFAULT,
        api_key: str | None = None, video: dict | None = None,
    ):
        self._client = client
        self._video = {k: v for k, v in (video or {}).items() if v}  # {"title", "channel"}: what the video is about
        self._api_key = api_key
        self.model = model if model in CLAUDE_MODELS else DEFAULT_CLAUDE_MODEL
        self._glossary = glossary.strip()
        self.target = languages.get(target)
        self.input_tokens = self.output_tokens = 0
        self.cost_usd = 0.0

    @property
    def client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(api_key=self._api_key) if self._api_key else anthropic.Anthropic()
        return self._client

    def _system(self) -> str:
        system = CLAUDE_SYSTEM_PROMPT.format(target=self.target.name_en)
        if self.target.code in SPEECH_NOTES:
            system += f"\n- {SPEECH_NOTES[self.target.code]}"
        if self._glossary:
            system += ("\nGlossary from the user — always translate these terms this way (one per line, "
                       f"\"term = translation\"):\n{self._glossary}")
        return system

    def _budget(self, seconds: float | None) -> int | None:
        # A little room above the natural pace: the voice may speak up to ~1.2x (timing.plan_rates).
        return max(8, round(seconds * languages.chars_per_second(self.target.code) * 1.15)) if seconds else None

    def _request(self, lines: list[dict], context: list[str]) -> list[str]:
        import anthropic

        payload = {
            "video": self._video,
            "context_before": context,
            "lines": [{"n": n + 1, "lang": ln.get("lang") or "unknown", "seconds": round(ln["seconds"], 1)
                       if ln.get("seconds") else None, "max_chars": self._budget(ln.get("seconds")),
                       "text": ln["text"]} for n, ln in enumerate(lines)],
        }
        params = {
            "model": self.model,
            "max_tokens": 64000,
            "system": self._system(),
            "output_config": {
                "effort": "medium",  # "low" read lines too literally; the whole video costs cents more
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
            "messages": [{"role": "user", "content": f"Translate these {len(lines)} lines into "
                          f"{self.target.name_en}:\n{json.dumps(payload, ensure_ascii=False)}"}],
        }
        if CLAUDE_MODELS[self.model].fallbacks:  # a declined request is re-run on a fallback model, same call
            params.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        try:
            with self.client.beta.messages.stream(**params) as stream:
                response = stream.get_final_message()
        except anthropic.AuthenticationError as exc:
            raise TranslatorUnavailable(f"Claude: the API key was not accepted ({exc})", code="auth") from exc
        except (anthropic.PermissionDeniedError, anthropic.NotFoundError) as exc:
            raise TranslatorUnavailable(f"Claude: the key may not use this model ({exc})", code="permission") from exc
        except anthropic.BadRequestError as exc:
            if "credit" in str(exc).lower():  # "Your credit balance is too low to access the Anthropic API"
                raise TranslatorUnavailable(f"Claude: no credit left ({exc})", code="credit") from exc
            raise
        except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.InternalServerError) as exc:
            raise TranslatorUnavailable(f"Claude unavailable ({exc})", code="unavailable") from exc
        except anthropic.APIStatusError as exc:
            if exc.status_code >= 500:
                raise TranslatorUnavailable(f"Claude unavailable ({exc})", code="unavailable") from exc
            raise
        self._count(response.usage)
        if response.stop_reason == "refusal":
            raise TranslatorUnavailable("Claude declined to translate this text", code="refusal")
        if response.stop_reason == "max_tokens":
            raise TranslatorUnavailable("Claude's translation was cut off (max_tokens)", code="unavailable")
        text = next(b.text for b in response.content if b.type == "text")
        out = [str(t).strip() for t in json.loads(text)["translations"]]
        if len(out) != len(lines):
            raise ValueError(f"expected {len(lines)} translations, got {len(out)}")
        return out

    def _count(self, usage) -> None:
        if usage is None:
            return
        tokens_in = (getattr(usage, "input_tokens", 0) or 0) + (getattr(usage, "cache_read_input_tokens", 0) or 0) \
            + (getattr(usage, "cache_creation_input_tokens", 0) or 0)
        tokens_out = getattr(usage, "output_tokens", 0) or 0
        self.input_tokens += tokens_in
        self.output_tokens += tokens_out
        price = CLAUDE_MODELS[self.model]
        self.cost_usd += (tokens_in * price.input_usd + tokens_out * price.output_usd) / 1e6

    def _chunk(self, lines: list[dict], context: list[str]) -> list[str]:
        try:
            return self._request(lines, context)
        except ValueError:
            if len(lines) == 1:
                raise
            half = len(lines) // 2  # count mismatch: halves almost always line up
            return self._chunk(lines[:half], context) + self._chunk(
                lines[half:], [ln["text"] for ln in lines[:half]][-self.CONTEXT_LINES:])

    def translate_video(self, lines: list[dict]) -> list[str]:
        """lines: [{"text", "lang", "seconds"}] in video order → one translation per line."""
        out: list[str] = []
        for start in range(0, len(lines), self.MAX_LINES):
            context = [ln["text"] for ln in lines[max(0, start - self.CONTEXT_LINES):start]]
            out.extend(self._chunk(lines[start:start + self.MAX_LINES], context))
        return out

    def translate_texts(self, texts: list[str]) -> list[str]:
        return self.translate_video([{"text": t, "lang": "", "seconds": None} for t in texts])

    def translate_group(self, lines: list[str], source: str = "") -> list[str]:
        return self.translate_video([{"text": t, "lang": source, "seconds": None} for t in lines])

    def translate_one(self, line: str, source: str) -> str:
        return self.translate_video([{"text": line, "lang": source, "seconds": None}])[0]


def check_claude_key(api_key: str, client=None) -> None:
    """Raise TranslatorUnavailable (code auth / permission / unavailable) unless the key works. Free: lists models."""
    import anthropic

    try:
        (client or anthropic.Anthropic(api_key=api_key, max_retries=1, timeout=20)).models.list(limit=1)
    except anthropic.AuthenticationError as exc:
        raise TranslatorUnavailable("The API key was not accepted", code="auth") from exc
    except anthropic.PermissionDeniedError as exc:
        raise TranslatorUnavailable("The API key has no permission", code="permission") from exc
    except (anthropic.APIConnectionError, anthropic.APIStatusError) as exc:
        raise TranslatorUnavailable(f"Couldn't reach Anthropic ({exc})", code="unavailable") from exc


def uses_claude(choice: str, api_key: str | None = None) -> bool:
    """Whether `make_backend(choice, ...)` starts with Claude."""
    key = api_key if api_key is not None else os.environ.get("ANTHROPIC_API_KEY", "")
    return choice == "claude" or (choice == "auto" and bool(key))


def make_backend(
    choice: str = "auto", claude_model: str = DEFAULT_CLAUDE_MODEL, glossary: str = "",
    target: str = languages.DEFAULT, api_key: str | None = None, video: dict | None = None,
) -> Translator:
    """The translator for a dub into `target`.

    auto = Claude if an API key is set, else free Google. Claude falls back to Google, Google to the offline NLLB
    model. "google" = free only, "offline" = NLLB only.
    """
    nllb = lambda: NllbBackend(target=target)  # noqa: E731 — built only if needed (1.4 GB model)
    google = lambda: GoogleBackend(target=target)  # noqa: E731
    if choice == "offline":
        return Translator(target, NllbBackend(target=target))
    if uses_claude(choice, api_key):
        key = api_key or os.environ.get("ANTHROPIC_API_KEY") or None
        claude = ClaudeBackend(model=claude_model, glossary=glossary, target=target, api_key=key, video=video)
        return Translator(target, claude, [google, nllb])
    return Translator(target, google(), [nllb])


def translate_segments(segments: list[Segment], backend) -> list[Segment]:
    """Fill `seg.ru` (the dub-language text). `backend` is a Translator, or any object with translate_texts()."""
    texts = [s.text for s in segments]
    if isinstance(backend, Translator):
        translated = backend.translate_texts(texts, [s.lang for s in segments], slots(segments))
    else:
        translated = backend.translate_texts(texts)
    if len(translated) != len(segments):
        raise RuntimeError(f"translator returned {len(translated)} lines for {len(segments)} segments")
    for seg, text in zip(segments, translated, strict=True):
        seg.ru = text
    return segments
