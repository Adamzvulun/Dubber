"""Runs all stages in order, caching each stage's result in `work/<video-id>/`.

If a run fails half-way (e.g. the internet drops), running it again skips the finished stages.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import align, languages, media, separate, subtitles, timing, transcribe, translate, tts
from .config import Settings
from .download import download, fetch_info, is_url, local_video_id
from .mux import mux
from .segments import load_segments, merge_into_sentences, save_segments, split_into_units

# (message in Russian, overall fraction 0..1)
ProgressFn = Callable[[str, float], None]

# Share of the total progress bar for each stage (transcription is the slow one on CPU). "separate" only runs when
# the original voice is removed (Settings.remove_voice); `stages()` gives the stages of one run.
STAGES = [
    ("download", "Скачиваю видео", 0.10),
    ("transcribe", "Распознаю речь", 0.40),
    ("translate", "Перевожу", 0.10),
    ("tts", "Озвучиваю", 0.20),
    ("align", "Подгоняю озвучку по времени", 0.10),
    ("separate", "Убираю оригинальный голос", 0.25),
    ("mux", "Собираю итоговое видео", 0.10),
]
# (video, out_wav, progress) -> out_wav: the original soundtrack without the voice
SeparateFn = Callable[..., Path]


def stages(remove_voice: bool = False) -> list[tuple[str, str, float]]:
    """The stages one run goes through, with weights that add up to 1."""
    active = [s for s in STAGES if s[0] != "separate" or remove_voice]
    total = sum(w for *_, w in active)
    return [(key, label, w / total) for key, label, w in active]


@dataclass
class Result:
    id: str  # this dub (= its folder in output/)
    title: str
    video: Path
    dub_srt: Path  # subtitles in the dub language
    src_srt: Path  # subtitles of what was said
    transcript: Path
    bilingual: Path
    folder: Path
    video_id: str = ""  # the video (= its folder in work/); several dubs can share it


def dub_id(video_id: str, lang: str, voice: str, background: bool, remove_voice: bool) -> str:
    """Name of one dub's folder in output/: each set of choices of a video is its own library entry.

    The same choices again give the same name, so redoing a dub replaces it instead of adding a duplicate.
    """
    choices = hashlib.sha1(f"{lang}|{voice}|{background}|{remove_voice}".encode()).hexdigest()[:6]
    return f"{video_id}--{lang}-{choices}"


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
    def __init__(self, callback: ProgressFn | None, remove_voice: bool = False):
        self.callback = callback
        self.done = 0.0
        self.stages = stages(remove_voice)

    def stage(self, key: str):
        label, weight = next((lbl, w) for k, lbl, w in self.stages if k == key)
        base = self.done
        self.done += weight

        def report(fraction: float) -> None:
            if self.callback:
                self.callback(label, min(1.0, base + weight * fraction))

        report(0.0)
        return report


def _info_file(dub_json: Path) -> Path:
    return dub_json.with_name(dub_json.stem + ".info.json")


def translation_info(dub_json: Path) -> dict:
    """Which engine translated a cached translation, its cost and why engines were skipped (for meta.json)."""
    info = {"translator": "", "model": "", "notes": [], "cost_usd": 0.0}
    try:
        info |= json.loads(_info_file(dub_json).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        legacy = dub_json.with_suffix(".translator")  # before 2026-10-17: the engine name only
        if legacy.exists():
            info["translator"] = legacy.read_text(encoding="utf-8")
    return info


def run(
    source: str,
    settings: Settings,
    progress: ProgressFn | None = None,
    translator: translate.Backend | None = None,
    synth: tts.SynthFn | None = None,
    transcriber: Callable[[Path], list] | None = None,
    separator: SeparateFn | None = None,
) -> Result:
    """Dub `source` (YouTube URL or local file). Backends can be injected (used by tests)."""
    media.require_ffmpeg()
    remove_voice = settings.keep_background and settings.remove_voice  # nothing to remove without a background
    p = _Progress(progress, remove_voice)

    # 1. Download into work/<id>/ (skipped when a previous run already has the video).
    report = p.stage("download")
    source_info = identify(source, settings.work_dir)
    video_id, title = source_info["id"], source_info["title"]
    work = settings.work_dir / video_id
    video = work / "source.mp4"
    if not video.exists():
        download(source, work, settings.max_height, progress=report)
    report(1.0)

    target = languages.get(settings.target_lang)
    voice = languages.voice_for(target.code, settings.voice)

    # 2. Transcribe (any language, several per video)
    report = p.stage("transcribe")
    # "_v3": every line carries its spoken language. Older caches came from Whisper forced to English (French parts
    # became gibberish English) or lacked line languages, so they are redone.
    src_json = work / "segments_src_v3.json"
    info_json = work / "speech_info.json"
    if not src_json.exists():
        audio = media.extract_audio(video, work / "audio_16k.wav")
        info: dict = {}
        if transcriber is not None:
            raw = transcriber(audio)
        else:
            raw = transcribe.transcribe(
                audio, settings.whisper_model, settings.whisper_device, progress=report, info_out=info
            )
        words = [w for seg in raw for w in seg.words]
        save_segments(split_into_units(words) if words else merge_into_sentences(raw), src_json)
        info_json.write_text(json.dumps(info), encoding="utf-8")
    segments = load_segments(src_json)
    speech = json.loads(info_json.read_text(encoding="utf-8")) if info_json.exists() else {}
    source_langs: list[str] = speech.get("languages") or ([speech["language"]] if speech.get("language") else [])
    source_lang = source_langs[0] if len(source_langs) == 1 else ""  # "" = unknown or several languages
    if not segments:
        raise RuntimeError("No speech found in this video")
    report(1.0)

    # 3. Translate
    report = p.stage("translate")
    # The free engines share one cache; a Claude translation has its own, keyed by model, glossary and prompt version,
    # so adding a key, editing the glossary or improving the prompt translates again. A Claude run that fell back to
    # Google is saved as a free one, so the next run tries Claude again (e.g. after credit was added).
    use_claude = translator is None and translate.uses_claude(settings.translator, settings.claude_key)
    glossary = settings.glossary() if use_claude else ""
    free_json = work / f"segments_{target.code}_v3.json"
    tag = hashlib.sha1(
        f"{settings.claude_model}\n{glossary}\n{translate.CLAUDE_PROMPT_VERSION}".encode()).hexdigest()[:8]
    claude_json = work / f"segments_{target.code}_v3_claude_{tag}.json"
    dub_json = claude_json if use_claude else free_json
    if not dub_json.exists():
        backend = translator or translate.make_backend(
            settings.translator, settings.claude_model, glossary, target=target.code, api_key=settings.claude_key,
            video={"title": title, "channel": source_info["channel"]})
        translate.translate_segments(segments, backend)
        name = getattr(backend, "name", "")
        dub_json = claude_json if name == "claude" else free_json
        save_segments(segments, dub_json)
        info = {"translator": name, "notes": getattr(backend, "notes", []),
                "cost_usd": getattr(backend, "cost_usd", 0.0),
                "model": settings.claude_model if name == "claude" else ""}
        _info_file(dub_json).write_text(json.dumps(info), encoding="utf-8")
    segments = load_segments(dub_json)
    translation = translation_info(dub_json)
    report(1.0)

    # 4. Text to speech
    report = p.stage("tts")
    # Two passes: speak every line at natural speed to measure it, plan one steady pace for the video
    # (timing.plan_rates), then speak again at the planned rates — Edge scales duration exactly by the rate.
    clips_dir = work / f"clips_{voice}"
    natural = tts.synthesize(segments, clips_dir, voice, synth=synth, progress=lambda f: report(f / 2))
    lengths = [align.speech_seconds(c) if c else None for c in natural]
    rates = timing.plan_rates(segments, lengths, settings.max_speedup)
    clips = tts.synthesize(segments, clips_dir, voice, synth=synth, rates=rates,
                           progress=lambda f: report(0.5 + f / 2))

    # 5. Align clips into one dubbed track (the voice name already identifies the language)
    report = p.stage("align")
    # Keyed by the lines' timing and text: any change to them can never reuse a stale track.
    key = hashlib.sha1(json.dumps([(s.start, s.end, s.ru) for s in segments]).encode()).hexdigest()[:10]
    track = work / f"dub_track_{voice}_{key}.wav"
    timing_json = work / f"timing_{voice}_{key}.json"
    if not track.exists() or not timing_json.exists():
        lines: list[dict] = []
        align.build_track(segments, clips, media.duration(video), track, progress=report, report=lines)
        for line in lines:
            line["rate"] = round(rates[line["index"]], 3)
        timing_json.write_text(json.dumps(timing_report(lines), ensure_ascii=False, indent=1), encoding="utf-8")

    # 6. Optional: the original soundtrack without the speaker's voice (cached per video, any dub language reuses it)
    background_audio = None
    if remove_voice:
        report = p.stage("separate")
        if media.has_audio(video):
            background_audio = (separator or separate.separate_background)(
                video, work / "background_htdemucs.wav", progress=report)

    # 7. Subtitles + final video, all in output/<dub id>/ (what the website's library reads)
    report = p.stage("mux")
    dub = dub_id(video_id, target.code, voice, settings.keep_background, background_audio is not None)
    folder = settings.output_dir / dub
    files = subtitles.write_all(segments, folder, title, target=target.code, source=source_lang)
    out_video = folder / "dubbed.mp4"
    partial = folder / "dubbed.partial.mp4"  # never serve a half-written file
    mux(
        video, track, partial, dub_srt=files["dub_srt"],
        original_volume=settings.original_volume, background=settings.keep_background,
        background_audio=background_audio, background_volume=settings.music_volume,
        dub_lang=target.iso3, dub_title=target.native,
        original_lang="mul" if len(source_langs) > 1 else languages.iso3(source_lang),
    )
    partial.replace(out_video)
    if not (folder / "thumbnail.jpg").exists():
        media.thumbnail(video, folder / "thumbnail.jpg")
    save_segments(segments, folder / "segments.json")
    shutil.copyfile(timing_json, folder / "timing.json")
    meta = {
        "id": dub,
        "video_id": video_id,
        "title": title,
        "channel": source_info["channel"],
        "source": source if is_url(source) else "",
        "duration": round(media.duration(video), 2),
        "voice": voice,
        "background": settings.keep_background,
        "remove_voice": background_audio is not None,
        "target_lang": target.code,
        "source_lang": source_lang,
        "source_langs": source_langs,
        "translator": translation["translator"],
        "translator_model": translation["model"],
        "translator_notes": translation["notes"],
        "translation_cost_usd": translation["cost_usd"],
        "files": {key: path.name for key, path in files.items()},
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    report(1.0)

    return Result(
        id=dub,
        title=title,
        video=out_video,
        dub_srt=files["dub_srt"],
        src_srt=files["src_srt"],
        transcript=files["transcript"],
        bilingual=files["bilingual"],
        folder=folder,
        video_id=video_id,
    )

