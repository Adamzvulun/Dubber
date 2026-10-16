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

    # Second run reuses the cache: no stage needs its backend again.
    again = pipeline.run(str(sample_video), settings, translator=None, synth=None, transcriber=None)
    assert again.video == result.video
