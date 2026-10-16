import json
import os
from types import SimpleNamespace

import pytest

from dubber.segments import Segment
from dubber.translate import (
    ClaudeBackend,
    FallbackBackend,
    GoogleBackend,
    OfflineBackend,
    _chunks,
    translate_segments,
)


def test_chunks_respect_limits():
    chunks = _chunks(["aaaa"] * 10, max_chars=12, max_items=100)
    assert all(sum(len(t) + 1 for t in c) <= 12 for c in chunks)
    assert sum(len(c) for c in chunks) == 10
    assert [len(c) for c in _chunks(["a"] * 5, max_chars=999, max_items=2)] == [2, 2, 1]


def test_google_batches_lines():
    calls = []

    def fake(text):
        calls.append(text)
        return "\n".join(f"RU:{ln}" for ln in text.split("\n"))

    out = GoogleBackend(fake).translate_texts(["one", "two", "three"])
    assert out == ["RU:one", "RU:two", "RU:three"]
    assert len(calls) == 1


def test_google_falls_back_when_lines_merge():
    def fake(text):
        return "merged" if "\n" in text else f"RU:{text}"

    assert GoogleBackend(fake).translate_texts(["a", "b"]) == ["RU:a", "RU:b"]


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


def test_translate_segments_sets_ru():
    segs = [Segment(0, 1, "Hi")]
    translate_segments(segs, GoogleBackend(lambda t: "Привет"))
    assert segs[0].ru == "Привет"


def test_google_rejects_robot_check_page():
    page = "<html><head><title>Sorry...</title></head><body>unusual traffic</body></html>"
    with pytest.raises(RuntimeError):
        GoogleBackend(lambda t: page).translate_texts(["Hello"])


class Boom:
    name = "boom"

    def translate_texts(self, texts):
        raise RuntimeError("blocked")


class Echo:
    name = "echo"

    def __init__(self):
        self.calls = 0

    def translate_texts(self, texts):
        self.calls += 1
        return [f"RU:{t}" for t in texts]


def test_fallback_switches_once_and_stays():
    echo = Echo()
    fb = FallbackBackend(Boom(), lambda: echo)
    assert fb.translate_texts(["a"]) == ["RU:a"]
    assert fb.name == "echo"
    assert fb.translate_texts(["b"]) == ["RU:b"] and echo.calls == 2


def test_fallback_keeps_primary_when_it_works():
    primary = Echo()
    fb = FallbackBackend(primary, lambda: pytest.fail("fallback should not be built"))
    assert fb.translate_texts(["a"]) == ["RU:a"] and fb.name == "echo"


@pytest.mark.network
@pytest.mark.skipif(not os.environ.get("DUBBER_NETWORK_TESTS"), reason="set DUBBER_NETWORK_TESTS=1")
def test_offline_backend_real_model():
    out = OfflineBackend().translate_texts(["Hello, this is a test.", ""])
    assert out[1] == "" and any(ch in out[0].lower() for ch in "привет")


def test_split_sentences():
    from dubber.translate import split_sentences

    assert split_sentences("Why? Because it burns. Really!") == ["Why?", "Because it burns.", "Really!"]
    assert split_sentences('He said "hi." Then left.') == ['He said "hi."', "Then left."]
    assert split_sentences("No end punctuation") == ["No end punctuation"]
    assert split_sentences("  ") == []


@pytest.mark.network
@pytest.mark.skipif(not os.environ.get("DUBBER_NETWORK_TESTS"), reason="set DUBBER_NETWORK_TESTS=1")
def test_offline_backend_keeps_every_sentence():
    out = OfflineBackend().translate_texts(["How do you soothe the burn? Why does wasabi make your eyes water?"])[0]
    assert out.count("?") == 2


def test_google_resends_a_line_left_in_another_language():
    """Mixed video: Google detects one language per request, so a French line may come back unchanged."""
    calls = []

    def fake(text):
        calls.append(text)
        if "\n" in text:
            return "\n".join("Bonjour" if ln == "Bonjour" else f"RU:{ln}" for ln in text.split("\n"))
        return "Здравствуйте"

    out = GoogleBackend(fake).translate_texts(["Hello", "Bonjour", "Thanks", "Bye"])
    assert out == ["RU:Hello", "Здравствуйте", "RU:Thanks", "RU:Bye"] and calls[-1] == "Bonjour"


def test_google_leaves_text_already_in_target_language():
    calls = []

    def echo(text):
        calls.append(text)
        return text

    assert GoogleBackend(echo).translate_texts(["Привет", "Пока"]) == ["Привет", "Пока"] and len(calls) == 1


def test_backend_choice_per_target(monkeypatch):
    from dubber.translate import make_backend

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert isinstance(make_backend("auto", target="ru"), FallbackBackend)  # offline en→ru fallback
    assert isinstance(make_backend("auto", target="he"), GoogleBackend)  # no offline model for Hebrew
    with pytest.raises(RuntimeError):
        make_backend("offline", target="he")


def test_claude_prompt_names_the_target_language():
    client = FakeClaude()
    ClaudeBackend(client=client, target="he").translate_texts(["Hello"])
    assert "Hebrew" in client.requests[0]["system"] and "Russian" not in client.requests[0]["system"]
