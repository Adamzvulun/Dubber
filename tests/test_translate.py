import json
import os
from types import SimpleNamespace

import pytest

from dubber import languages
from dubber.segments import Segment
from dubber.translate import (
    ClaudeBackend,
    GoogleBackend,
    NllbBackend,
    Translator,
    TranslatorUnavailable,
    UntranslatedError,
    _chunks,
    needs_retry,
    translate_segments,
)


def test_chunks_respect_limits():
    chunks = _chunks(["aaaa"] * 10, max_chars=12, max_items=100)
    assert all(sum(len(t) + 1 for t in c) <= 12 for c in chunks)
    assert sum(len(c) for c in chunks) == 10
    assert [len(c) for c in _chunks(["a"] * 5, max_chars=999, max_items=2)] == [2, 2, 1]


def fake_google(answer, calls=None):
    """fetch(text, source, target) stand-in: `answer(line, source)` per line, joined like Google does."""
    def fetch(text, source, target):
        if calls is not None:
            calls.append((text, source, target))
        return "\n".join(answer(line, source) for line in text.split("\n"))
    return fetch


def test_google_batches_lines_and_names_target():
    calls = []
    g = GoogleBackend("he", fetch=fake_google(lambda ln, s: f"HE:{ln}", calls))
    assert g.translate_group(["one", "two", "three"], "en") == ["HE:one", "HE:two", "HE:three"]
    assert calls == [("one\ntwo\nthree", "en", "iw")]  # one request; Google's code for Hebrew is "iw"


def test_google_retries_robot_check_then_gives_up():
    attempts, waits = [], []

    def refusing(text, source, target):
        attempts.append(text)
        if len(attempts) < 3:
            raise TranslatorUnavailable("HTTP 429")
        return "ok"

    g = GoogleBackend("ru", fetch=refusing, sleep=waits.append)
    assert g.translate_group(["x"]) == ["ok"] and waits == [2, 4]

    def always(text, source, target):
        raise TranslatorUnavailable("HTTP 429")

    with pytest.raises(TranslatorUnavailable):
        GoogleBackend("ru", fetch=always, sleep=lambda s: None).translate_group(["x"])


def test_google_rejects_robot_check_page(monkeypatch):
    import requests

    page = SimpleNamespace(status_code=200, text="<html><body>Our systems have detected unusual traffic</body></html>")
    monkeypatch.setattr(requests, "get", lambda *a, **k: page)
    with pytest.raises(TranslatorUnavailable):
        GoogleBackend._http("Hello", "auto", "ru")


class FakeClaude:
    """Mimics client.beta.messages.create for the structured-output call."""

    def __init__(self, drop_first_time=False):
        self.requests = []
        self.drop_first_time = drop_first_time
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.requests.append(kwargs)
        lines = kwargs["messages"][0]["content"].split("\n")[1:]
        out = [f"RU:{ln.split('. ', 1)[1]}" for ln in lines]
        if self.drop_first_time and len(self.requests) == 1:
            out = out[:-1]
        block = SimpleNamespace(type="text", text=json.dumps({"translations": out}, ensure_ascii=False))
        return SimpleNamespace(stop_reason="end_turn", content=[block])


def test_claude_backend_and_request_shape():
    client = FakeClaude()
    out = ClaudeBackend(model="claude-opus-5-5", client=client).translate_texts(["Hello.", "World."])
    assert out == ["RU:Hello.", "RU:World."]
    req = client.requests[0]
    assert req["model"] == "claude-opus-5-5"
    assert req["output_config"]["format"]["type"] == "json_schema"
    assert req["fallbacks"] == "default"


def test_claude_retries_in_halves_on_count_mismatch():
    client = FakeClaude(drop_first_time=True)
    out = ClaudeBackend(client=client).translate_texts(["a", "b", "c", "d"])
    assert out == ["RU:a", "RU:b", "RU:c", "RU:d"]
    assert len(client.requests) == 3


def test_claude_refusal_raises():
    client = FakeClaude()
    client.beta.messages.create = lambda **kw: SimpleNamespace(stop_reason="refusal", content=[])
    with pytest.raises(RuntimeError):
        ClaudeBackend(client=client).translate_texts(["x"])


def test_translate_segments_with_plain_backend():
    segs = [Segment(0, 1, "Hi")]
    translate_segments(segs, SimpleNamespace(translate_texts=lambda texts: ["Привет"]))
    assert segs[0].ru == "Привет"


def test_split_sentences():
    from dubber.translate import split_sentences

    assert split_sentences("Why? Because it burns. Really!") == ["Why?", "Because it burns.", "Really!"]
    assert split_sentences('He said "hi." Then left.') == ['He said "hi."', "Then left."]
    assert split_sentences("No end punctuation") == ["No end punctuation"]
    assert split_sentences("  ") == []


class FakeEngine:
    def __init__(self, name, answer):
        self.name, self.answer, self.groups = name, answer, []

    def translate_group(self, lines, source=""):
        self.groups.append((source, list(lines)))
        return [self.answer(line, source) for line in lines]

    def translate_one(self, line, source):
        return self.answer(line, source)


def test_lines_are_batched_by_spoken_language_and_target_language_kept():
    engine = FakeEngine("google", lambda ln, s: f"Перевод {ln}")
    t = Translator("ru", engine)
    texts = ["Hello there", "Bonjour à tous", "Je fais du pain", "Привет всем", "Thanks a lot"]
    out = t.translate_texts(texts, ["en", "fr", "fr", "ru", "en"])
    assert out[3] == "Привет всем"  # already Russian: untouched, never sent
    assert engine.groups == [("en", ["Hello there"]), ("fr", ["Bonjour à tous", "Je fais du pain"]),
                             ("en", ["Thanks a lot"])]


def test_unavailable_primary_falls_back_for_the_rest():
    def refuse(ln, s):
        raise TranslatorUnavailable("robot check")

    primary, backup = FakeEngine("google", refuse), FakeEngine("offline", lambda ln, s: f"Резерв {ln}")
    t = Translator("ru", primary, lambda: backup)
    out = t.translate_texts(["Hello you all", "Bonjour à tous"], ["en", "fr"])
    assert out == ["Резерв Hello you all", "Резерв Bonjour à tous"] and t.name == "offline"
    assert len(primary.groups) == 1  # after the first refusal Google isn't asked again


def test_quality_gate_resends_untranslated_line_then_fails_loudly():
    # Google leaves the French line as it is (mixed-language request); the gate re-sends it alone.
    sent = []

    def answer(ln, s):
        sent.append((ln, s))
        return ln if s == "fr" and len(sent) == 1 else f"Перевод {ln}"

    t = Translator("ru", FakeEngine("google", answer))
    assert t.translate_texts(["Je fais du pain ici"], ["fr"]) == ["Перевод Je fais du pain ici"]

    stubborn = Translator("ru", FakeEngine("google", lambda ln, s: ln))  # never translates, no fallback
    with pytest.raises(UntranslatedError):
        stubborn.translate_texts(["Je fais du pain ici"], ["fr"])


def test_needs_retry_rules():
    ru, es = languages.get("ru"), languages.get("es")
    assert needs_retry("Je fais du pain ici", "Je fais du pain ici", "fr", ru)  # untranslated
    assert needs_retry("Bonjour à tous", "Bonjour", "fr", ru)  # no Cyrillic in a Russian dub
    assert not needs_retry("Paris.", "Париж.", "fr", ru)
    assert not needs_retry("OK.", "OK.", "en", es)  # short, Latin target: may legitimately stay the same
    assert needs_retry("Hello there", "", "en", es)
    assert not needs_retry("...", "...", "en", ru)  # nothing to translate


def test_backend_choice(monkeypatch):
    from dubber.translate import make_backend

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    t = make_backend("auto", target="he")
    assert isinstance(t.primary, GoogleBackend) and t.primary.target.code == "he" and t._fallback_factory


@pytest.mark.network
@pytest.mark.skipif(not os.environ.get("DUBBER_NETWORK_TESTS"), reason="set DUBBER_NETWORK_TESTS=1")
def test_nllb_real_model_any_pair():
    out = NllbBackend("he").translate_group(["Bonjour à tous. Je fais du pain ici depuis vingt ans."], "fr")[0]
    assert any("\u0590" <= c <= "\u05ff" for c in out) and len(out) > 20


def test_claude_prompt_names_the_target_language():
    client = FakeClaude()
    ClaudeBackend(client=client, target="he").translate_texts(["Hello"])
    assert "Hebrew" in client.requests[0]["system"] and "Russian" not in client.requests[0]["system"]


def test_gate_accepts_a_line_google_says_is_already_in_the_dub_language():
    # Whisper mislabelled an English line as French; dubbing into English, Google returns it unchanged and
    # reports "en" as its language: keep it instead of failing.
    def fetch(text, source, target):
        return (text, "en")

    t = Translator("en", GoogleBackend("en", fetch=fetch))
    assert t.translate_texts(["So patience and good flour are the secret."], ["fr"]) == [
        "So patience and good flour are the secret."]
