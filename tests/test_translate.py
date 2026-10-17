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
    """Mimics client.beta.messages.stream(...) for the structured-output call: answers "РУ:<text>" per line."""

    def __init__(self, drop_first_time=False, stop_reason="end_turn", error=None):
        self.requests = []
        self.drop_first_time = drop_first_time
        self.stop_reason = stop_reason
        self.error = error
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self.stream))

    @staticmethod
    def payload(request):
        return json.loads(request["messages"][0]["content"].split("\n", 1)[1])

    def stream(self, **kwargs):
        self.requests.append(kwargs)
        if self.error is not None:
            raise self.error
        out = [f"РУ:{line['text']}" for line in self.payload(kwargs)["lines"]]
        if self.drop_first_time and len(self.requests) == 1:
            out = out[:-1]
        block = SimpleNamespace(type="text", text=json.dumps({"translations": out}, ensure_ascii=False))
        usage = SimpleNamespace(input_tokens=1000, output_tokens=500, cache_read_input_tokens=0,
                                cache_creation_input_tokens=0)
        message = SimpleNamespace(stop_reason=self.stop_reason, content=[block], usage=usage)

        class Stream:
            def __enter__(self):
                return SimpleNamespace(get_final_message=lambda: message)

            def __exit__(self, *exc):
                return False

        return Stream()


def test_claude_backend_and_request_shape():
    client = FakeClaude()
    out = ClaudeBackend(model="claude-opus-5-5", client=client).translate_texts(["Hello.", "World."])
    assert out == ["РУ:Hello.", "РУ:World."]
    req = client.requests[0]
    assert req["model"] == "claude-opus-5-5"
    assert req["output_config"]["format"]["type"] == "json_schema" and req["output_config"]["effort"] == "low"
    assert req["fallbacks"] == "default" and req["betas"] == ["server-side-fallback-2026-07-01"]


def test_claude_haiku_has_no_server_side_fallback_and_unknown_model_uses_default():
    client = FakeClaude()
    ClaudeBackend(model="claude-haiku-5-5", client=client).translate_texts(["Hi"])
    assert "fallbacks" not in client.requests[0]
    assert ClaudeBackend(model="gpt-whatever", client=client).model == "claude-opus-5-5"


def test_claude_gets_the_whole_video_with_languages_slots_and_budgets():
    client = FakeClaude()
    engine = ClaudeBackend(client=client, target="ru", glossary="sourdough = закваска")
    t = Translator("ru", engine)
    segs = [Segment(0.0, 2.0, "Hello there friends", lang="en"), Segment(3.0, 5.5, "Je fais du pain", lang="fr"),
            Segment(6.0, 8.0, "Привет всем", lang="ru"), Segment(8.5, 10.0, "Sourdough is alive", lang="en")]
    translate_segments(segs, t)
    assert len(client.requests) == 1  # one request for the whole mixed-language video
    lines = FakeClaude.payload(client.requests[0])["lines"]
    assert [ln["lang"] for ln in lines] == ["en", "fr", "en"]  # the Russian line is kept, not sent
    assert lines[0]["seconds"] == 2.9  # its slot: until shortly before the next line (timing.slots)
    assert lines[0]["max_chars"] == round(2.85 * 14 * 1.15)
    assert "sourdough = закваска" in client.requests[0]["system"]
    assert [s.ru for s in segs] == ["РУ:Hello there friends", "РУ:Je fais du pain", "Привет всем",
                                    "РУ:Sourdough is alive"]
    assert t.name == "claude" and t.cost_usd == round((1000 * 4 + 500 * 20) / 1e6, 4)


def test_claude_long_video_is_chunked_with_context():
    client = FakeClaude()
    engine = ClaudeBackend(client=client)
    engine.MAX_LINES = 3
    out = engine.translate_video([{"text": f"Line {i}", "lang": "en", "seconds": 2.0} for i in range(7)])
    assert out == [f"РУ:Line {i}" for i in range(7)] and len(client.requests) == 3
    assert FakeClaude.payload(client.requests[1])["context_before"] == ["Line 0", "Line 1", "Line 2"]


def test_claude_retries_in_halves_on_count_mismatch():
    client = FakeClaude(drop_first_time=True)
    out = ClaudeBackend(client=client).translate_texts(["a", "b", "c", "d"])
    assert out == ["РУ:a", "РУ:b", "РУ:c", "РУ:d"]
    assert len(client.requests) == 3


def test_claude_refusal_is_unavailable():
    with pytest.raises(TranslatorUnavailable) as err:
        ClaudeBackend(client=FakeClaude(stop_reason="refusal")).translate_texts(["x"])
    assert err.value.code == "refusal"


def api_error(cls, status, message):
    import httpx2

    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls(message, response=httpx2.Response(status, request=request), body=None)


@pytest.mark.parametrize("error,code", [
    ("auth", "auth"), ("credit", "credit"), ("overloaded", "unavailable"), ("connection", "unavailable"),
])
def test_claude_errors_fall_back_to_google_with_a_reason(error, code):
    import anthropic

    errors = {
        "auth": lambda: api_error(anthropic.AuthenticationError, 401, "invalid x-api-key"),
        "credit": lambda: api_error(anthropic.BadRequestError, 400,
                                    "Your credit balance is too low to access the Anthropic API."),
        "overloaded": lambda: api_error(anthropic.InternalServerError, 529, "Overloaded"),
        "connection": lambda: anthropic.APIConnectionError(request=None),
    }
    google = FakeEngine("google", lambda ln, s: f"Перевод {ln}")
    t = Translator("ru", ClaudeBackend(client=FakeClaude(error=errors[error]())), [lambda: google, None])
    assert t.translate_texts(["Hello you all"], ["en"], [2.0]) == ["Перевод Hello you all"]
    assert t.name == "google" and t.notes == [f"claude:{code}"]


def test_claude_other_bad_request_is_a_real_error():
    import anthropic

    t = Translator("ru", ClaudeBackend(client=FakeClaude(error=api_error(anthropic.BadRequestError, 400, "bad"))),
                   [lambda: FakeEngine("google", lambda ln, s: ln)])
    with pytest.raises(anthropic.BadRequestError):
        t.translate_texts(["Hello you all"], ["en"])


def test_check_claude_key():
    import anthropic

    from dubber.translate import check_claude_key

    ok = SimpleNamespace(models=SimpleNamespace(list=lambda **kw: []))
    check_claude_key("sk-ant-good", client=ok)

    def refuse(**kw):
        raise api_error(anthropic.AuthenticationError, 401, "invalid x-api-key")

    with pytest.raises(TranslatorUnavailable) as err:
        check_claude_key("sk-ant-bad", client=SimpleNamespace(models=SimpleNamespace(list=refuse)))
    assert err.value.code == "auth"


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
    assert isinstance(t.primary, GoogleBackend) and t.primary.target.code == "he" and len(t._factories) == 1
    t = make_backend("auto", target="he", api_key="sk-ant-x", claude_model="claude-sonnet-5-5", glossary="a = b")
    assert isinstance(t.primary, ClaudeBackend) and t.primary.model == "claude-sonnet-5-5"
    assert len(t._factories) == 2  # → Google → offline
    assert isinstance(make_backend("google", api_key="sk-ant-x").primary, GoogleBackend)  # "free only"


@pytest.mark.network
@pytest.mark.skipif(not os.environ.get("DUBBER_NETWORK_TESTS"), reason="set DUBBER_NETWORK_TESTS=1")
def test_nllb_real_model_any_pair():
    out = NllbBackend("he").translate_group(["Bonjour à tous. Je fais du pain ici depuis vingt ans."], "fr")[0]
    assert any("\u0590" <= c <= "\u05ff" for c in out) and len(out) > 20


def test_claude_prompt_names_the_target_language():
    client = FakeClaude()
    ClaudeBackend(client=client, target="he").translate_texts(["Hello"])
    assert "Hebrew" in client.requests[0]["system"] and "Russian" not in client.requests[0]["system"]
    assert "Glossary" not in client.requests[0]["system"]


def test_gate_accepts_a_line_google_says_is_already_in_the_dub_language():
    # Whisper mislabelled an English line as French; dubbing into English, Google returns it unchanged and
    # reports "en" as its language: keep it instead of failing.
    def fetch(text, source, target):
        return (text, "en")

    t = Translator("en", GoogleBackend("en", fetch=fetch))
    assert t.translate_texts(["So patience and good flour are the secret."], ["fr"]) == [
        "So patience and good flour are the secret."]
