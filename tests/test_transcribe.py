import sys
import types

import numpy as np

from dubber import transcribe


def test_transcribe_passes_decoded_samples(tmp_path, tone, monkeypatch):
    """Regression: never hand faster-whisper a file path (its PyAV loader broke with av 19)."""
    wav = tone(tmp_path / "a.wav", 1.0)
    seen = {}

    class FakeModel:
        def __init__(self, *a, **k):
            pass

        def transcribe(self, audio, **kw):
            seen["audio"] = audio
            seen["word_timestamps"] = kw.get("word_timestamps")
            word = types.SimpleNamespace(start=0.1, end=0.6, word=" Hello.")
            seg = types.SimpleNamespace(start=0.0, end=1.0, text=" Hello. ", words=[word])
            return iter([seg]), types.SimpleNamespace(duration=1.0)

    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=FakeModel))
    segs = transcribe.transcribe(wav, "tiny")
    assert isinstance(seen["audio"], np.ndarray) and abs(len(seen["audio"]) - 16000) < 200
    assert segs[0].text == "Hello."
    assert seen["word_timestamps"] is True and (segs[0].words[0].start, segs[0].words[0].text) == (0.1, " Hello.")
