import json
from types import SimpleNamespace

import pytest

from dubber.segments import Segment
from dubber.translate import ClaudeBackend, GoogleBackend, _chunks, translate_segments


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
