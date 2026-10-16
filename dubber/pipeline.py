"""Runs all stages in order, caching each stage's result in `work/<video-id>/`.

If a run fails half-way (e.g. the internet drops), running it again skips the finished stages.
"""

from __future__ import annotations

import json
import re
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import align, media, subtitles, timing, transcribe, translate, tts
from .config import Settings
from .download import download, fetch_info, is_url, local_video_id
from .mux import mux
from .segments import load_segments, merge_into_sentences, save_segments, split_into_units

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
    id: str
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


_YOUTUBE_ID = re.compile(r"(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|embed/|live/)|youtu\.be/)([A-Za-z0-9_-]{11})")


def youtube_id(url: str) -> str | None:
    match = _YOUTUBE_ID.search(url)
    return match.group(1) if match else None


def identify(source: str, work_dir: Path | None = None) -> dict:
    """{id, title, channel} for a URL or a local file, without downloading the video.

    For YouTube links the id comes from the link and the details are cached in work/<id>/info.json,
    so a video that was already processed never needs YouTube again.
    """
    if is_url(source):
        vid = youtube_id(source)
        cached = work_dir / vid / "info.json" if (vid and work_dir) else None
        if cached and cached.exists():
            return json.loads(cached.read_text(encoding="utf-8"))
        info = fetch_info(source)
        result = {"id": info["id"], "title": info.get("title") or info["id"], "channel": info.get("channel") or ""}
        if work_dir:
            (work_dir / result["id"]).mkdir(parents=True, exist_ok=True)
            (work_dir / result["id"] / "info.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        return result
    path = Path(source).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"Not a URL and not an existing file: {source}")
    return {"id": local_video_id(path), "title": path.stem, "channel": ""}


def timing_report(lines: list[dict]) -> dict:
    """How well the dub keeps the speaker's timing (saved as output/<id>/timing.json)."""
    delays = [line["delay"] for line in lines]
    rates = sorted(line["rate"] for line in lines)
    return {
        "lines": len(lines),
        "median_rate": rates[len(rates) // 2] if rates else 1.0,
        "max_rate": rates[-1] if rates else 1.0,
        "late_lines": sum(d > 0.3 for d in delays),  # started >0.3 s after the speaker
        "max_delay": max(delays, default=0.0),
        "stretched_lines": sum(line["stretch"] > 1.01 for line in lines),
        "detail": lines,
    }


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
    source_info = identify(source, settings.work_dir)
    video_id, title = source_info["id"], source_info["title"]
    work = settings.work_dir / video_id
    video = work / "source.mp4"
    if not video.exists():
        download(source, work, settings.max_height, progress=report)
    report(1.0)

    # 2. Transcribe (English)
    report = p.stage("transcribe")
    # "_v2": lines are cut from word timings (segments.split_into_units); older caches used Whisper's chunks.
    en_json = work / "segments_en_v2.json"
    if not en_json.exists():
        audio = media.extract_audio(video, work / "audio_16k.wav")
        if transcriber is not None:
            raw = transcriber(audio)
        else:
            raw = transcribe.transcribe(audio, settings.whisper_model, settings.whisper_device, progress=report)
        words = [w for seg in raw for w in seg.words]
        save_segments(split_into_units(words) if words else merge_into_sentences(raw), en_json)
    segments = load_segments(en_json)
    if not segments:
        raise RuntimeError("В видео не найдено английской речи.")  # no English speech found
    report(1.0)

    # 3. Translate
    report = p.stage("translate")
    ru_json = work / "segments_ru_v2.json"
    if not ru_json.exists():
        backend = translator or translate.make_backend(settings.translator, settings.claude_model)
        translate.translate_segments(segments, backend)
        save_segments(segments, ru_json)
    segments = load_segments(ru_json)
    report(1.0)

    # 4. Text to speech
    report = p.stage("tts")
    # Two passes: speak every line at natural speed to measure it, plan one steady pace for the video
    # (timing.plan_rates), then speak again at the planned rates — Edge scales duration exactly by the rate.
    clips_dir = work / f"clips_{settings.voice}"
    natural = tts.synthesize(segments, clips_dir, settings.voice, synth=synth, progress=lambda f: report(f / 2))
    lengths = [align.speech_seconds(c) if c else None for c in natural]
    rates = timing.plan_rates(segments, lengths, settings.max_speedup)
    clips = tts.synthesize(segments, clips_dir, settings.voice, synth=synth, rates=rates,
                           progress=lambda f: report(0.5 + f / 2))

    # 5. Align clips into one Russian track
    report = p.stage("align")
    track = work / f"russian_track_v3_{settings.voice}.wav"
    timing_json = work / f"timing_v3_{settings.voice}.json"
    if not track.exists() or not timing_json.exists():
        lines: list[dict] = []
        align.build_track(segments, clips, media.duration(video), track, progress=report, report=lines)
        for line in lines:
            line["rate"] = round(rates[line["index"]], 3)
        timing_json.write_text(json.dumps(timing_report(lines), ensure_ascii=False, indent=1), encoding="utf-8")

    # 6. Subtitles + final video, all in output/<id>/ (what the website's library reads)
    report = p.stage("mux")
    folder = settings.output_dir / video_id
    files = subtitles.write_all(segments, folder, title)
    out_video = folder / "dubbed.mp4"
    partial = folder / "dubbed.partial.mp4"  # never serve a half-written file
    mux(
        video, track, partial, ru_srt=files["ru_srt"],
        original_volume=settings.original_volume, background=settings.keep_background,
    )
    partial.replace(out_video)
    if not (folder / "thumbnail.jpg").exists():
        media.thumbnail(video, folder / "thumbnail.jpg")
    save_segments(segments, folder / "segments.json")
    shutil.copyfile(timing_json, folder / "timing.json")
    meta = {
        "id": video_id,
        "title": title,
        "channel": source_info["channel"],
        "source": source if is_url(source) else "",
        "duration": round(media.duration(video), 2),
        "voice": settings.voice,
        "background": settings.keep_background,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    report(1.0)

    return Result(
        id=video_id,
        title=title,
        video=out_video,
        ru_srt=files["ru_srt"],
        en_srt=files["en_srt"],
        transcript=files["transcript"],
        bilingual=files["bilingual"],
        folder=folder,
    )

