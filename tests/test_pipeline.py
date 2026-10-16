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


async def stub_synth(text, voice, out_path):
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
        capture_output=True, text=True, check=True).stdout)
    kinds = [s["codec_type"] for s in info["streams"]]
    assert kinds.count("video") == 1 and kinds.count("audio") == 2 and kinds.count("subtitle") == 1
    assert abs(float(info["format"]["duration"]) - 6.0) < 0.3
    langs = [s.get("tags", {}).get("language") for s in info["streams"] if s["codec_type"] == "audio"]
    assert langs == ["rus", "eng"]

    srt = result.ru_srt.read_text(encoding="utf-8")
    assert "Русский 0" in srt and "Русский 1" in srt and "Русский 2" not in srt  # 3 fragments -> 2 sentences
    assert result.transcript.exists() and result.bilingual.exists()

    assert (result.folder / "meta.json").exists() and (result.folder / "thumbnail.jpg").exists()
    assert (result.folder / "subtitles_ru.vtt").read_text(encoding="utf-8").startswith("WEBVTT")

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

    async def recording_synth(text, voice, out_path):
        voices_used.append(voice)
        await stub_synth(text, voice, out_path)

    for voice in ("ru-RU-DmitryNeural", "ru-RU-SvetlanaNeural"):
        settings = Settings(work_dir=tmp_path / "work", output_dir=tmp_path / "out", voice=voice)
        pipeline.run(str(sample_video), settings, translator=StubTranslator(), synth=recording_synth,
                     transcriber=stub_transcriber)
    assert "ru-RU-SvetlanaNeural" in voices_used and "ru-RU-DmitryNeural" in voices_used
