"""Stage 6 — build the final MP4: video + dubbed audio (original quietly underneath) + subtitles."""

from __future__ import annotations

from pathlib import Path

from .media import has_audio, probe, run_ffmpeg


def mux(
    video: Path,
    dub_wav: Path,
    out_mp4: Path,
    dub_srt: Path | None = None,
    original_volume: float = 0.15,
    keep_original_track: bool = True,
    background: bool = True,
    dub_lang: str = "rus",
    dub_title: str = "Русский",
    original_lang: str = "eng",
) -> Path:
    """Write `out_mp4`.

    Audio track 1 (default): the dubbed voice mixed over the original at `original_volume`
    (or the voice alone when `background` is False).
    Audio track 2 (optional): the untouched original, selectable in any player.
    Subtitle track: the dub language, soft (can be turned on/off in the player).
    Language tags are ISO 639-2 codes (`languages.Language.iso3`, `languages.iso3`).
    """
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    original_has_audio = has_audio(video)

    args = ["-i", str(video), "-i", str(dub_wav)]
    if dub_srt:
        args += ["-i", str(dub_srt)]

    if original_has_audio and background:
        args += [
            "-filter_complex",
            f"[0:a]volume={original_volume}[bg];[1:a]apad[fg];"
            "[bg][fg]amix=inputs=2:duration=first:normalize=0[dub]",
            "-map", "0:v:0", "-map", "[dub]",
        ]
        if keep_original_track:
            args += ["-map", "0:a:0"]
    elif original_has_audio:  # dubbed voice only, padded to the video's length
        duration = probe(video)["format"]["duration"]
        args += ["-filter_complex", f"[1:a]apad,atrim=0:{duration}[dub]", "-map", "0:v:0", "-map", "[dub]"]
        if keep_original_track:
            args += ["-map", "0:a:0"]
    else:
        args += ["-filter_complex", "[1:a]apad[dub]", "-map", "0:v:0", "-map", "[dub]", "-shortest"]
        keep_original_track = False

    if dub_srt:
        args += ["-map", "2:s:0", "-c:s", "mov_text", "-metadata:s:s:0", f"language={dub_lang}"]

    args += [
        "-c:v", "copy",
        "-c:a:0", "aac", "-b:a:0", "160k",
        "-metadata:s:a:0", f"language={dub_lang}", "-metadata:s:a:0", f"title={dub_title}",
        "-disposition:a:0", "default",
    ]
    if keep_original_track:
        args += [
            "-c:a:1", "copy",  # the original is kept as-is (no re-encoding: faster, no quality loss)
            "-metadata:s:a:1", f"language={original_lang}", "-metadata:s:a:1", "title=Original",
            "-disposition:a:1", "0",
        ]
    args += ["-movflags", "+faststart", str(out_mp4)]
    run_ffmpeg(args)
    return out_mp4
