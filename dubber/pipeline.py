"""Runs all stages in order, caching each stage's result in `work/<video-id>/`.

If a run fails half-way (e.g. the internet drops), running it again skips the finished stages.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import align, media, subtitles, transcribe, translate, tts
from .config import Settings
from .download import download, fetch_info, is_url, local_video_id
from .mux import mux
from .segments import load_segments, merge_into_sentences, save_segments

# (message in Russian, overall fraction 0..1)
ProgressFn = Callable[[str, float], None]

# Share of the total progress bar for each stage (transcription is the slow one on CPU).
STAGES = [
    ("download", "Скачиваю видео", 0.10),
    ("transcribe", "Распознаю английскую речь", 0.40),
    ("translate", "Перевожу на русский", 0.10),
    ("tts", "Озвучиваю по-русски", 0.20),
    ("align", "Подгоняю озвучку по времени", 0.10),
    ("mux", "Собираю итоговое видео", 0.10),
]


@dataclass
class Result:
    title: str
    video: Path
    ru_srt: Path
    en_srt: Path
    transcript: Path
    bilingual: Path
    folder: Path


def safe_name(title: str, max_len: int = 80) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", title).strip().rstrip(".")
    return (name or "video")[:max_len].strip()


def identify(source: str) -> tuple[str, str]:
    """(cache id, title) for a URL or a local file, without downloading the video."""
    if is_url(source):
        meta = fetch_info(source)
        return meta["id"], meta.get("title") or meta["id"]
    path = Path(source).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"Not a URL and not an existing file: {source}")
    return local_video_id(path), path.stem


class _Progress:
    def __init__(self, callback: ProgressFn | None):
        self.callback = callback
        self.done = 0.0

    def stage(self, key: str):
        label, weight = next((lbl, w) for k, lbl, w in STAGES if k == key)
        base = self.done
        self.done += weight

        def report(fraction: float) -> None:
            if self.callback:
                self.callback(label, min(1.0, base + weight * fraction))

        report(0.0)
        return report


def run(
    source: str,
    settings: Settings,
    progress: ProgressFn | None = None,
    translator: translate.Backend | None = None,
    synth: tts.SynthFn | None = None,
    transcriber: Callable[[Path], list] | None = None,
) -> Result:
    """Dub `source` (YouTube URL or local file). Backends can be injected (used by tests)."""
    media.require_ffmpeg()
    p = _Progress(progress)

    # 1. Download into work/<id>/ (skipped when a previous run already has the video).
    report = p.stage("download")
    video_id, title = identify(source)
    work = settings.work_dir / video_id
    video = work / "source.mp4"
    if not video.exists():
        download(source, work, settings.max_height, progress=report)
    report(1.0)

    # 2. Transcribe (English)
    report = p.stage("transcribe")
    en_json = work / "segments_en.json"
    if not en_json.exists():
        audio = media.extract_audio(video, work / "audio_16k.wav")
        if transcriber is not None:
            raw = transcriber(audio)
        else:
            raw = transcribe.transcribe(audio, settings.whisper_model, settings.whisper_device, progress=report)
        save_segments(merge_into_sentences(raw), en_json)
    segments = load_segments(en_json)
    if not segments:
        raise RuntimeError("В видео не найдено английской речи.")  # no English speech found
    report(1.0)

    # 3. Translate
    report = p.stage("translate")
    ru_json = work / "segments_ru.json"
    if not ru_json.exists():
        backend = translator or translate.make_backend(settings.translator, settings.claude_model)
        translate.translate_segments(segments, backend)
        save_segments(segments, ru_json)
    segments = load_segments(ru_json)
    report(1.0)

    # 4. Text to speech
    report = p.stage("tts")
    clips = tts.synthesize(segments, work / "clips", settings.voice, synth=synth, progress=report)

    # 5. Align clips into one Russian track
    report = p.stage("align")
    track = work / f"russian_track_{settings.voice}.wav"
    if not track.exists():
        align.build_track(segments, clips, media.duration(video), track, settings.max_speedup, progress=report)

    # 6. Subtitles + final video
    report = p.stage("mux")
    folder = settings.output_dir / safe_name(title)
    files = subtitles.write_all(segments, folder, title)
    out_video = folder / f"{safe_name(title)} (RU).mp4"
    mux(video, track, out_video, ru_srt=files["ru_srt"], original_volume=settings.original_volume)
    report(1.0)

    return Result(
        title=title,
        video=out_video,
        ru_srt=files["ru_srt"],
        en_srt=files["en_srt"],
        transcript=files["transcript"],
        bilingual=files["bilingual"],
        folder=folder,
    )

