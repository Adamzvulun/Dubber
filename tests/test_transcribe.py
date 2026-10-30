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
    monkeypatch.setattr(transcribe, "language_runs", lambda model, samples, checker=None: [(0.0, 1.0, "en")])
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
    monkeypatch.setattr(transcribe, "language_runs",
                        lambda model, samples, checker=None: [(0.5, 1.5, "en"), (2.0, 3.0, "fr")])
    info = {}
    segs = transcribe.transcribe(wav, "tiny", info_out=info)
    assert calls == [("en", 1.8), ("fr", 2.2)]  # each run + up to 1 s, never past the middle of the pause
    assert [round(s.start, 2) for s in segs] == [0.3, 2.05] and round(segs[1].words[0].start, 2) == 2.05
    assert set(info["languages"]) == {"en", "fr"}


def test_stray_language_guesses_are_relabelled_to_the_video_languages(monkeypatch):
    """Real Hebrew speech: Whisper called some regions Italian/French with middling confidence (2026-10-18)."""
    hebrew = [(0, 6, {"he": 0.46, "ka": 0.21}), (6, 12, {"it": 0.55, "he": 0.10}), (12, 20, {"he": 0.92}),
              (20, 26, {"fr": 0.68, "he": 0.12}), (26, 40, {"he": 0.99}), (40, 44, {"lv": 0.50, "he": 0.05})]
    assert transcribe.video_languages(hebrew) == {"he"}
    mixed = [(0, 10, {"en": 0.98}), (10, 20, {"fr": 0.99}), (20, 30, {"en": 0.97}), (30, 34, {"fr": 0.97})]
    assert transcribe.video_languages(mixed) == {"en", "fr"}
    quote = [(0, 60, {"en": 0.99}), (60, 63, {"fr": 0.95}), (63, 120, {"en": 0.99})]  # a short sure quote stays
    assert transcribe.video_languages(quote) == {"en", "fr"}

    class Detector:
        def __init__(self, pieces):
            self.pieces = iter(pieces)

        def detect_language(self, audio):
            probs = next(self.pieces)[2]
            lang = max(probs, key=probs.get)
            return lang, probs[lang], list(probs.items())

    regions = [{"start": int(a * 16000), "end": int(b * 16000)} for a, b, _ in hebrew]
    import faster_whisper.vad as vad
    monkeypatch.setattr(vad, "get_speech_timestamps", lambda samples, options: regions)
    assert transcribe.language_runs(Detector(hebrew), np.zeros(16000 * 44, np.float32)) == [(0.0, 44.0, "he")]


def test_a_foreign_line_the_detector_is_unsure_of_is_checked_by_the_bigger_model(monkeypatch):
    """Spanish lines in an English film, under noise (measured 2026-10-30): "base" called a 2.3-s Spanish line
    Portuguese 0.24 and the run went to English (then misheard and transliterated, Adam's check.json); "small" heard
    Spanish 0.93. Short lines are left alone: on a 1.3-s "¿Qué pasa?" neither model was sure."""
    film = [(0, 30, {"en": 0.99}), (30, 32.3, {"pt": 0.24, "es": 0.21, "en": 0.18}), (32.3, 60, {"en": 0.98}),
            (60, 61.3, {"ru": 0.39, "es": 0.09}), (61.3, 90, {"en": 0.97}), (90, 93, {"it": 0.6, "en": 0.2}),
            (93, 120, {"en": 0.99})]
    second_opinion = {30.0: {"es": 0.93, "en": 0.02}, 90.0: {"en": 0.7, "it": 0.2}}
    checked = []

    class Detector:
        def __init__(self, answers):
            self.answers = answers

        def detect_language(self, audio):
            probs = self.answers(len(audio) / 16000)
            lang = max(probs, key=probs.get)
            return lang, probs[lang], list(probs.items())

    regions = [{"start": int(a * 16000), "end": int(b * 16000)} for a, b, _ in film]
    import faster_whisper.vad as vad
    monkeypatch.setattr(vad, "get_speech_timestamps", lambda samples, options: regions)

    def region(seconds):  # the regions all differ in length
        return next((a, probs) for a, b, probs in film if round(b - a, 1) == round(seconds, 1))

    def base(seconds):
        return region(seconds)[1]

    def small(seconds):
        start = region(seconds)[0]
        checked.append(start)
        return second_opinion[start]

    runs = transcribe.language_runs(Detector(base), np.zeros(16000 * 120, np.float32), checker=Detector(small))
    runs = [(round(a, 1), round(b, 1), lang) for a, b, lang in runs]
    assert runs == [(0, 30, "en"), (30, 32.3, "es"), (32.3, 120, "en")]
    assert checked == [30.0, 90.0]  # only regions long enough whose best guess is not a language of the video


def test_nvidia_card_without_its_libraries_falls_back_to_the_processor(tmp_path, tone, monkeypatch):
    """A PC with an NVIDIA card but no cuBLAS/cuDNN: ctranslate2 picks the card and fails on first use (Adam's new PC,
    2026-10-29). The dub must go on with the processor, and later dubs must not try the card again."""
    wav = tone(tmp_path / "a.wav", 1.0)
    devices = []

    class FakeModel:
        def __init__(self, size, device, compute_type):
            devices.append((size, device, compute_type))
            self.device = device

        def transcribe(self, audio, **kw):
            if self.device != "cpu":
                raise RuntimeError("Library cublas64_12.dll is not found or cannot be loaded")
            seg = types.SimpleNamespace(start=0.0, end=1.0, text="Hi", words=[])
            return iter([seg]), None

    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=FakeModel))
    monkeypatch.setattr(transcribe, "language_runs", lambda model, samples, checker=None: [(0.0, 1.0, "en")])
    monkeypatch.setattr(transcribe, "_gpu_failed", False)
    assert transcribe.transcribe(wav, "tiny")[0].text == "Hi"
    assert devices[-1][1:] == ("cpu", "int8") and any(d[1] == "auto" for d in devices)
    devices.clear()
    transcribe.transcribe(wav, "tiny")
    assert {d[1] for d in devices} == {"cpu"}  # remembered: straight to the processor


def test_other_whisper_errors_are_not_hidden(tmp_path, tone, monkeypatch):
    wav = tone(tmp_path / "a.wav", 1.0)

    class FakeModel:
        def __init__(self, *a, **k):
            pass

        def transcribe(self, audio, **kw):
            raise RuntimeError("out of memory")

    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=FakeModel))
    monkeypatch.setattr(transcribe, "language_runs", lambda model, samples, checker=None: [(0.0, 1.0, "en")])
    monkeypatch.setattr(transcribe, "_gpu_failed", False)
    import pytest
    with pytest.raises(RuntimeError, match="out of memory"):
        transcribe.transcribe(wav, "tiny")


def test_gpu_errors_are_recognised():
    assert transcribe.gpu_error(RuntimeError("Library cublas64_12.dll is not found or cannot be loaded"))
    assert transcribe.gpu_error(RuntimeError("Could not load library cudnn_ops64_9.dll. Error code 126"))
    assert transcribe.gpu_error(RuntimeError("CUDA failed with error unknown error"))
    assert not transcribe.gpu_error(RuntimeError("out of memory"))


def test_reader_hears_a_clip_and_falls_back_to_the_processor(tmp_path, tone, monkeypatch):
    """The original voice's listen-back check (clone.py): one model, loaded once; a broken card -> processor."""
    wav = tone(tmp_path / "a.wav", 1.0)
    devices, asked = [], []

    class FakeModel:
        def __init__(self, size, device, compute_type):
            devices.append(device)
            self.device = device

        def transcribe(self, audio, **kw):
            asked.append(kw["language"])
            if self.device != "cpu":
                raise RuntimeError("Library cublas64_12.dll is not found or cannot be loaded")
            return iter([types.SimpleNamespace(text=" Привет,"), types.SimpleNamespace(text=" мир.")]), None

        def detect_language(self, audio):  # an English accent: Whisper is less sure it is Russian
            return "ru", 0.62, [("ru", 0.62), ("en", 0.3)]

    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=FakeModel))
    monkeypatch.setattr(transcribe, "_gpu_failed", False)
    read = transcribe.reader("small", "auto")
    assert read(wav, "ru") == "Привет, мир."
    heard = read(wav, "ru")
    assert heard == "Привет, мир." and heard.native == 0.62
    assert read(wav, "xx").native == 1.0  # a language Whisper doesn't know: no judgement
    assert devices == ["auto", "cpu"] and set(asked) == {"ru", "xx"}
