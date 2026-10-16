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
    monkeypatch.setattr(transcribe, "language_runs", lambda model, samples: [(0.0, 1.0, "en")])
    segs = transcribe.transcribe(wav, "tiny")
    assert isinstance(seen["audio"], np.ndarray) and abs(len(seen["audio"]) - 16000) < 200
    assert segs[0].text == "Hello."
    assert seen["word_timestamps"] is True and (segs[0].words[0].start, segs[0].words[0].text) == (0.1, " Hello.")


def test_language_runs_join_pieces_and_fill_unsure_ones():
    pieces = [(0, 5, "en", 0.99), (5, 7, "en", 0.95), (7.5, 20, "fr", 0.97), (20.5, 21, "de", 0.3), (25, 30, "en", 0.9)]
    assert transcribe.merge_runs(pieces) == [(0, 7, "en"), (7.5, 21, "fr"), (25, 30, "en")]
    assert transcribe.merge_runs([(0, 1, "xx", 0.1), (1, 3, "ru", 0.9)]) == [(0, 3, "ru")]


def test_mixed_language_audio_is_transcribed_run_by_run(tmp_path, tone, monkeypatch):
    """Each language run is transcribed in its own language, with timestamps shifted back to the full audio."""
    wav = tone(tmp_path / "a.wav", 4.0)
    calls = []

    class FakeModel:
        def __init__(self, *a, **k):
            pass

        def transcribe(self, audio, **kw):
            calls.append((kw["language"], round(len(audio) / 16000, 1)))
            word = types.SimpleNamespace(start=0.3, end=0.6, word=" mot")
            seg = types.SimpleNamespace(start=0.3, end=0.6, text=" mot", words=[word])
            return iter([seg]), types.SimpleNamespace(duration=len(audio) / 16000)

    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=FakeModel))
    monkeypatch.setattr(transcribe, "language_runs", lambda model, samples: [(0.5, 1.5, "en"), (2.0, 3.0, "fr")])
    info = {}
    segs = transcribe.transcribe(wav, "tiny", info_out=info)
    assert calls == [("en", 1.4), ("fr", 1.4)]  # each run ± 0.2 s
    assert [round(s.start, 2) for s in segs] == [0.6, 2.1] and round(segs[1].words[0].start, 2) == 2.1
    assert set(info["languages"]) == {"en", "fr"}
