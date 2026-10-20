"""End-to-end run of the real pipeline code (download of a local file, ffmpeg, alignment, mux).

Network services (Whisper model download, Google/Claude, Microsoft TTS) are replaced by local stubs,
so this test runs offline. It checks the plumbing, not translation or voice quality.
"""

import asyncio
import json
import subprocess

from dubber import pipeline
from dubber.config import Settings
from dubber.segments import Segment


class StubTranslator:
    name = "stub"

    def translate_texts(self, texts):
        return [f"Русский {i}" for i, _ in enumerate(texts)]


async def stub_synth(text, voice, out_path, rate="+0%"):
    await asyncio.to_thread(
        subprocess.run,
        ["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=600:duration=1.2",
         str(out_path)],
        check=True,
    )


def stub_transcriber(audio):
    return [Segment(0.5, 2.0, "Hello and welcome."), Segment(2.5, 4.0, "This is a"), Segment(4.1, 5.0, "test.")]


def test_end_to_end_with_local_file(tmp_path, sample_video):
    settings = Settings(work_dir=tmp_path / "work", output_dir=tmp_path / "out")
    seen = []
    result = pipeline.run(
        str(sample_video), settings, progress=lambda label, f: seen.append(f),
        translator=StubTranslator(), synth=stub_synth, transcriber=stub_transcriber,
    )

    assert seen[-1] == 1.0 and seen == sorted(seen)
    info = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(result.video)],
        capture_output=True, text=True, encoding="utf-8", check=True).stdout)
    kinds = [s["codec_type"] for s in info["streams"]]
    assert kinds.count("video") == 1 and kinds.count("audio") == 2 and kinds.count("subtitle") == 1
    assert abs(float(info["format"]["duration"]) - 6.0) < 0.3
    langs = [s.get("tags", {}).get("language") for s in info["streams"] if s["codec_type"] == "audio"]
    assert langs == ["rus", "und"]  # the stub transcriber reports no language

    srt = result.dub_srt.read_text(encoding="utf-8")
    assert "Русский 0" in srt and "Русский 1" in srt and "Русский 2" not in srt  # 3 fragments -> 2 sentences
    assert result.transcript.exists() and result.bilingual.exists()

    assert (result.folder / "meta.json").exists() and (result.folder / "thumbnail.jpg").exists()
    assert (result.folder / "subtitles_ru.vtt").read_text(encoding="utf-8").startswith("WEBVTT")
    report = json.loads((result.folder / "timing.json").read_text(encoding="utf-8"))
    assert report["lines"] == 2 and report["late_lines"] == 0

    # Second run reuses the cache: no stage needs its backend again.
    again = pipeline.run(str(sample_video), settings, translator=None, synth=None, transcriber=None)
    assert again.video == result.video


def test_without_background_russian_voice_only(tmp_path, sample_video):
    """Opt-in: no original sound under the Russian voice (the English track stays available separately)."""
    import numpy as np

    from dubber.media import decode_audio, run_ffmpeg

    settings = Settings(work_dir=tmp_path / "work", output_dir=tmp_path / "out", keep_background=False)
    result = pipeline.run(str(sample_video), settings, translator=StubTranslator(), synth=stub_synth,
                          transcriber=stub_transcriber)
    dub = tmp_path / "dub.wav"
    run_ffmpeg(["-i", str(result.video), "-map", "0:a:0", "-ac", "1", "-ar", "16000", str(dub)])
    audio = decode_audio(dub, 16000)
    # The sample's 300 Hz tone fills the whole original track; without background, the gap before the
    # first Russian phrase (0.0-0.5 s) must be silent.
    assert float(np.abs(audio[: int(0.4 * 16000)]).mean()) < 1e-3
    assert abs(len(audio) / 16000 - 6.0) < 0.3


def test_remove_voice_puts_the_voice_free_background_under_the_dub(tmp_path, sample_video):
    """Opt-in Demucs stage: the separated background (here a stand-in: a 900 Hz tone) replaces the original."""
    import numpy as np

    from dubber.media import decode_audio, run_ffmpeg

    calls, labels = [], []

    def stub_separator(video, out_wav, progress=None):
        calls.append(video)
        run_ffmpeg(["-f", "lavfi", "-i", "sine=frequency=900:duration=6", "-ac", "2", "-ar", "44100", str(out_wav)])
        progress(1.0)
        return out_wav

    settings = Settings(work_dir=tmp_path / "work", output_dir=tmp_path / "out", remove_voice=True)
    result = pipeline.run(str(sample_video), settings, progress=lambda label, f: labels.append(label),
                          translator=StubTranslator(), synth=stub_synth, transcriber=stub_transcriber,
                          separator=stub_separator)
    assert len(calls) == 1 and "Убираю оригинальный голос" in labels
    assert json.loads((result.folder / "meta.json").read_text(encoding="utf-8"))["remove_voice"] is True
    dub = tmp_path / "dub.wav"
    run_ffmpeg(["-i", str(result.video), "-map", "0:a:0", "-ac", "1", "-ar", "16000", str(dub)])
    head = decode_audio(dub, 16000)[: int(0.4 * 16000)]  # before the first dubbed line: background only
    spectrum = np.abs(np.fft.rfft(head))
    freqs = np.fft.rfftfreq(len(head), 1 / 16000)
    assert abs(freqs[spectrum.argmax()] - 900) < 10  # the separated background, not the original 300 Hz tone
    kinds = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", str(result.video)],
        capture_output=True, text=True, encoding="utf-8", check=True).stdout)["streams"]
    assert [s["codec_type"] for s in kinds].count("subtitle") == 1  # inputs shifted by one: subtitles still mapped


def test_stages_weights_add_up_with_and_without_voice_separation():
    for separate in (False, True):
        active = pipeline.stages(separate)
        assert abs(sum(w for *_, w in active) - 1) < 1e-9
        assert ("separate" in [k for k, *_ in active]) is separate


def test_lines_are_cut_from_word_timings(tmp_path, sample_video):
    """With Whisper word timings, a chunk holding two sentences becomes two lines with speech-only bounds."""
    from dubber.segments import Word

    def worded_transcriber(audio):
        words = [Word(0.6, 0.9, " Hello"), Word(1.0, 1.4, " there."),
                 Word(2.6, 3.0, " Second"), Word(3.1, 3.6, " one.")]
        return [Segment(0.0, 5.0, "Hello there. Second one.", words=words)]

    settings = Settings(work_dir=tmp_path / "work", output_dir=tmp_path / "out")
    result = pipeline.run(str(sample_video), settings, translator=StubTranslator(), synth=stub_synth,
                          transcriber=worded_transcriber)
    lines = json.loads((result.folder / "segments.json").read_text(encoding="utf-8"))
    assert [(x["start"], x["end"], x["text"]) for x in lines] == [(0.6, 1.4, "Hello there."), (2.6, 3.6, "Second one.")]


def test_youtube_id_and_cached_identify(tmp_path, monkeypatch):
    assert pipeline.youtube_id("https://www.youtube.com/watch?v=qD0_yWgifDM&t=5s") == "qD0_yWgifDM"
    assert pipeline.youtube_id("https://youtu.be/qD0_yWgifDM") == "qD0_yWgifDM"
    assert pipeline.youtube_id("https://www.youtube.com/shorts/qD0_yWgifDM") == "qD0_yWgifDM"
    assert pipeline.youtube_id("https://vimeo.com/123") is None

    calls = []
    monkeypatch.setattr(pipeline, "fetch_info", lambda url: calls.append(url) or {"id": "qD0_yWgifDM", "title": "T"})
    url = "https://youtu.be/qD0_yWgifDM"
    assert pipeline.identify(url, tmp_path)["title"] == "T"
    assert pipeline.identify(url, tmp_path)["title"] == "T"  # second time from the cache, no network
    assert len(calls) == 1


def test_each_voice_gets_its_own_recordings(tmp_path, sample_video):
    """Regression: re-dubbing with another voice must not reuse the first voice's cached clips."""
    voices_used = []

    async def recording_synth(text, voice, out_path, rate="+0%"):
        voices_used.append(voice)
        await stub_synth(text, voice, out_path, rate)

    for voice in ("ru-RU-DmitryNeural", "ru-RU-SvetlanaNeural"):
        settings = Settings(work_dir=tmp_path / "work", output_dir=tmp_path / "out", voice=voice)
        pipeline.run(str(sample_video), settings, translator=StubTranslator(), synth=recording_synth,
                     transcriber=stub_transcriber)
    assert "ru-RU-SvetlanaNeural" in voices_used and "ru-RU-DmitryNeural" in voices_used


def test_voice_speaks_at_planned_rate_and_clips_follow_text(tmp_path):
    """Second pass passes the planned Edge rate; a changed line never reuses an old recording."""
    from dubber import tts

    calls = []

    async def fake(text, voice, out_path, rate="+0%"):
        calls.append((text, rate))
        out_path.write_bytes(b"x")

    lines = [Segment(0, 1, "a", "один"), Segment(1, 2, "b", "")]
    natural = tts.synthesize(lines, tmp_path, synth=fake)
    fast = tts.synthesize(lines, tmp_path, synth=fake, rates=[1.35, 1.0])
    assert calls == [("один", "+0%"), ("один", "+35%")] and natural[1] is None and fast[0] != natural[0]
    lines[0].ru = "два"
    assert tts.synthesize(lines, tmp_path, synth=fake)[0] != natural[0]


class NoAudioReceived(Exception):
    """Same name as edge_tts.exceptions.NoAudioReceived."""


def test_one_silent_line_does_not_fail_the_dub(tmp_path):
    """Edge randomly returns no audio (~9%); after retries the line stays silent instead of failing the video."""
    from dubber import tts

    attempts = []

    async def flaky(text, voice, out_path, rate="+0%"):
        attempts.append(text)
        if text == "никогда":
            raise NoAudioReceived("No audio was received.")
        if text == "иногда" and attempts.count(text) < 3:
            raise NoAudioReceived("No audio was received.")
        out_path.write_bytes(b"x")

    lines = [Segment(i, i + 1, "en", ru) for i, ru in enumerate(["один", "иногда", "никогда", "…", "два", "три"])]
    clips = tts.synthesize(lines, tmp_path, synth=flaky, retries=3)
    assert [c is not None for c in clips] == [True, True, False, False, True, True]
    assert attempts.count("никогда") == 4 and "…" not in attempts  # punctuation is never sent


def test_rated_line_falls_back_to_natural_clip(tmp_path):
    from dubber import tts

    async def fails_when_fast(text, voice, out_path, rate="+0%"):
        if rate != "+0%":
            raise NoAudioReceived("No audio was received.")
        out_path.write_bytes(b"x")

    lines = [Segment(0, 1, "en", "один")]
    natural = tts.synthesize(lines, tmp_path, synth=fails_when_fast)
    assert tts.synthesize(lines, tmp_path, synth=fails_when_fast, rates=[1.4], retries=1) == natural


def test_voice_outage_is_reported_not_silenced(tmp_path):
    import pytest

    from dubber import tts

    async def down(text, voice, out_path, rate="+0%"):
        raise NoAudioReceived("No audio was received.")

    lines = [Segment(i, i + 1, "en", "слово") for i in range(5)]
    with pytest.raises(RuntimeError, match="No audio"):
        tts.synthesize(lines, tmp_path, synth=down, retries=0)


def test_dub_into_hebrew_from_french(tmp_path, sample_video, monkeypatch):
    """Another dub language: Hebrew voice, Hebrew tags, language-coded files, meta records both languages."""
    from dubber import transcribe

    voices = []

    async def synth(text, voice, out_path, rate="+0%"):
        voices.append(voice)
        await stub_synth(text, voice, out_path, rate)

    def fake_transcribe(audio, *a, info_out=None, **k):
        info_out.update(language="fr", languages=["fr"])
        return [Segment(0.5, 2.0, "Bonjour à tous."), Segment(2.5, 4.0, "C'est un test.")]

    monkeypatch.setattr(transcribe, "transcribe", fake_transcribe)
    settings = Settings(work_dir=tmp_path / "work", output_dir=tmp_path / "out", target_lang="he", voice="female")
    result = pipeline.run(str(sample_video), settings, translator=StubTranslator(), synth=synth)

    assert set(voices) == {"he-IL-HilaNeural"}
    meta = json.loads((result.folder / "meta.json").read_text(encoding="utf-8"))
    assert meta["target_lang"] == "he" and meta["source_lang"] == "fr"
    assert meta["files"]["dub_vtt"] == "subtitles_he.vtt" and (result.folder / "subtitles_he.vtt").exists()
    assert "FR" in (result.folder / meta["files"]["bilingual"]).read_text(encoding="utf-8")
    info = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", str(result.video)],
        capture_output=True, text=True, encoding="utf-8", check=True).stdout)
    tags = [(s["codec_type"], s.get("tags", {}).get("language")) for s in info["streams"] if s["codec_type"] != "video"]
    assert tags == [("audio", "heb"), ("audio", "fre"), ("subtitle", "heb")]


class NamedTranslator:
    """Stands in for translate.Translator: `name` says which engine ended up translating."""

    def __init__(self, name, notes=(), cost=0.0):
        self.name, self.notes, self.cost_usd, self.calls = name, list(notes), cost, 0

    def translate_texts(self, texts, langs=None, seconds=None):
        self.calls += 1
        return [f"Русский {i}" for i, _ in enumerate(texts)]


def test_claude_translation_cache_cost_and_fallback(tmp_path, sample_video, monkeypatch):
    from dubber import translate

    made = []

    def fake_make_backend(choice, model, glossary, target, api_key, video):
        made.append((choice, model, glossary, api_key))
        assert video == {"title": "sample", "channel": ""}  # the topic goes to Claude
        return engines.pop(0)

    monkeypatch.setattr(translate, "make_backend", fake_make_backend)
    glossary = tmp_path / "glossary.txt"
    glossary.write_text("sourdough = закваска", encoding="utf-8")
    settings = Settings(work_dir=tmp_path / "work", output_dir=tmp_path / "out", claude_key="sk-ant-test",
                        glossary_file=glossary, translator="auto")
    run = lambda: pipeline.run(str(sample_video), settings, synth=stub_synth, transcriber=stub_transcriber)  # noqa: E731

    # 1. Claude fails (no credit) and Google translates: saved as a free translation, the reason is kept.
    engines = [NamedTranslator("google", notes=["claude:credit"])]
    meta = json.loads((run().folder / "meta.json").read_text(encoding="utf-8"))
    assert meta["translator"] == "google" and meta["translator_notes"] == ["claude:credit"]
    assert made[-1] == ("auto", "claude-opus-5-5", "sourdough = закваска", "sk-ant-test")

    # 2. Next run tries Claude again (credit added): its own cache, with model and cost.
    engines = [NamedTranslator("claude", cost=0.0812)]
    meta = json.loads((run().folder / "meta.json").read_text(encoding="utf-8"))
    assert meta["translator"] == "claude" and meta["translator_model"] == "claude-opus-5-5"
    assert meta["translation_cost_usd"] == 0.0812 and len(made) == 2

    # 3. Same settings: the Claude translation is reused (no new request, no new cost).
    run()
    assert len(made) == 2

    # 4. Glossary edited: translated again.
    glossary.write_text("sourdough = опара", encoding="utf-8")
    engines = [NamedTranslator("claude", cost=0.05)]
    run()
    assert len(made) == 3

    # 5. A new prompt version translates again.
    monkeypatch.setattr(translate, "CLAUDE_PROMPT_VERSION", translate.CLAUDE_PROMPT_VERSION + 1)
    engines = [NamedTranslator("claude", cost=0.05)]
    run()
    assert len(made) == 4

    # 6. Without a key the free cache from step 1 is used.
    settings.claude_key = ""
    meta = json.loads((run().folder / "meta.json").read_text(encoding="utf-8"))
    assert meta["translator"] == "google" and len(made) == 4


def test_each_dub_of_a_video_keeps_its_own_library_entry(tmp_path, sample_video):
    # Adam dubbed one video twice (other language and voice); both library cards played the newest dub.
    def dub(**choices):
        settings = Settings(work_dir=tmp_path / "work", output_dir=tmp_path / "out", **choices)
        return pipeline.run(str(sample_video), settings, translator=StubTranslator(), synth=stub_synth,
                            transcriber=stub_transcriber)

    ru = dub()
    en = dub(target_lang="en", voice="female")
    assert ru.id != en.id and ru.folder != en.folder and ru.video_id == en.video_id
    for result, lang in ((ru, "ru"), (en, "en")):
        meta = json.loads((result.folder / "meta.json").read_text(encoding="utf-8"))
        assert meta["id"] == result.id and meta["video_id"] == ru.video_id and meta["target_lang"] == lang
        assert result.video.exists() and result.folder.name == result.id
    assert dub().id == ru.id  # the same choices again replace that dub
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == sorted([ru.id, en.id])


def test_dub_id_is_a_safe_name_that_changes_with_every_choice():
    import re

    base = dict(video_id="dQw4w9WgXcQ", lang="ru", voice="ru-RU-DmitryNeural", background=True, remove_voice=False)
    one = pipeline.dub_id(**base)
    assert one == pipeline.dub_id(**base) and one.startswith("dQw4w9WgXcQ--ru-")
    assert re.fullmatch(r"[A-Za-z0-9_-]{1,64}", pipeline.dub_id(**{**base, "video_id": "local-0123456789ab"}))
    changed = [dict(lang="en"), dict(voice="ru-RU-SvetlanaNeural"), dict(background=False), dict(remove_voice=True)]
    assert len({one, *(pipeline.dub_id(**{**base, **c}) for c in changed)}) == 5


def test_dub_id_of_an_unusual_video_id_is_still_a_safe_name():
    # yt-dlp ids of other sites can be long or contain dots, spaces, non-ASCII: the library could not open them.
    import re

    for vid in ("a" * 70, "lecture.final v2", "видео", "x/../y"):
        name = pipeline.dub_id(vid, "ru", "ru-RU-DmitryNeural", True, False)
        assert re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name), name
    assert pipeline.dub_id("a" * 70, "ru", "v", True, False) != pipeline.dub_id("a" * 71, "ru", "v", True, False)


def stub_separator_with_vocals(calls):
    from dubber.media import run_ffmpeg

    def separator(video, out_wav, progress=None, vocals_wav=None):
        calls.append(vocals_wav)
        run_ffmpeg(["-f", "lavfi", "-i", "sine=frequency=900:duration=6", "-ac", "2", "-ar", "44100", str(out_wav)])
        if vocals_wav:
            run_ffmpeg(["-f", "lavfi", "-i", "sine=frequency=200:duration=6", "-ac", "2", "-ar", "44100",
                        str(vocals_wav)])
        return out_wav
    return separator


def test_original_voice_copies_the_speaker(tmp_path, sample_video):
    """The opt-in original voice (clone.py): the separated voice track is its reference; the dub gets its own entry."""
    from dubber import clone
    from dubber.media import write_wav

    separated, cloned, labels = [], [], []

    def stub_cloner(segments, vocals_wav, lang, clips_dir, max_speedup, progress=None):
        cloned.append((vocals_wav, lang, clips_dir.name))
        clips_dir.mkdir(parents=True, exist_ok=True)
        clips = []
        for i, _ in enumerate(segments):
            clips.append(write_wav([0.1] * 24000, clips_dir / f"{i}.wav"))
        progress(1.0)
        return clips, [1.0] * len(segments)

    settings = Settings(work_dir=tmp_path / "work", output_dir=tmp_path / "out", voice=clone.VOICE)
    result = pipeline.run(str(sample_video), settings, progress=lambda label, f: labels.append(label),
                          translator=StubTranslator(), synth=stub_synth, transcriber=stub_transcriber,
                          separator=stub_separator_with_vocals(separated), cloner=stub_cloner)
    assert separated and separated[0].name == "vocals_htdemucs.wav"
    assert cloned == [(separated[0], "ru", "clips_original_ru")]
    meta = json.loads((result.folder / "meta.json").read_text(encoding="utf-8"))
    assert meta["voice"] == clone.VOICE and meta["voice_notes"] == [] and meta["remove_voice"] is False
    # the voice is separated before the dub is spoken (it is the reference), not after
    assert labels.index("Убираю оригинальный голос") < labels.index("Озвучиваю")
    edge = pipeline.run(str(sample_video), Settings(work_dir=tmp_path / "work", output_dir=tmp_path / "out"),
                        translator=StubTranslator(), synth=stub_synth, transcriber=stub_transcriber)
    assert edge.id != result.id


def test_original_voice_falls_back_to_edge(tmp_path, sample_video, monkeypatch):
    from dubber import clone

    def broken_cloner(*args, **kwargs):
        raise RuntimeError("CUDA error: no kernel image is available")

    def run(cloner, **choices):
        settings = Settings(work_dir=tmp_path / "work", output_dir=tmp_path / "out", voice=clone.VOICE, **choices)
        result = pipeline.run(str(sample_video), settings, translator=StubTranslator(), synth=stub_synth,
                              transcriber=stub_transcriber, separator=stub_separator_with_vocals([]), cloner=cloner)
        return json.loads((result.folder / "meta.json").read_text(encoding="utf-8"))

    hebrew = run(broken_cloner, target_lang="he")  # not offered for Hebrew: the cloner isn't even asked
    assert hebrew["voice"] == "he-IL-AvriNeural" and hebrew["voice_notes"] == ["clone:language"]
    failed = run(broken_cloner)
    assert failed["voice"] == "ru-RU-DmitryNeural" and failed["voice_notes"] == ["clone:failed"]

    def broken_separator(video, out_wav, progress=None, vocals_wav=None):
        raise OSError("Connection reset while downloading the separation model")

    settings = Settings(work_dir=tmp_path / "w2", output_dir=tmp_path / "o2", voice=clone.VOICE)
    result = pipeline.run(str(sample_video), settings, translator=StubTranslator(), synth=stub_synth,
                          transcriber=stub_transcriber, separator=broken_separator, cloner=broken_cloner)
    no_voice = json.loads((result.folder / "meta.json").read_text(encoding="utf-8"))
    assert no_voice["voice"] == "ru-RU-DmitryNeural" and no_voice["voice_notes"] == ["clone:failed"]

    monkeypatch.setattr(clone, "ready", lambda: False)
    missing = run(None)
    assert missing["voice"] == "ru-RU-DmitryNeural" and missing["voice_notes"] == ["clone:not_installed"]


def test_the_voice_is_split_off_first_when_it_is_copied():
    assert [k for k, *_ in pipeline.stages(True, voice_first=True)] == [
        "download", "transcribe", "translate", "separate", "tts", "align", "mux"]
    assert [k for k, *_ in pipeline.stages(True)][-2:] == ["separate", "mux"]
    assert [k for k, *_ in pipeline.stages(False, voice_first=True)] == [k for k, *_ in pipeline.stages(False)]
