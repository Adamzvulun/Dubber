"""Stage 6 — build the final MP4: video + Russian audio (original quietly underneath) + subtitles."""

from __future__ import annotations

from pathlib import Path

from .media import has_audio, run_ffmpeg


def mux(
    video: Path,
    russian_wav: Path,
    out_mp4: Path,
    ru_srt: Path | None = None,
    original_volume: float = 0.15,
    keep_original_track: bool = True,
) -> Path:
    """Write `out_mp4`.

    Audio track 1 (default): Russian voice mixed over the original at `original_volume`.
    Audio track 2 (optional): the untouched English original, selectable in any player.
    Subtitle track: Russian, soft (can be turned on/off in the player).
    """
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    original_has_audio = has_audio(video)

    args = ["-i", str(video), "-i", str(russian_wav)]
    if ru_srt:
        args += ["-i", str(ru_srt)]

    if original_has_audio:
        args += [
            "-filter_complex",
            f"[0:a]volume={original_volume}[bg];[1:a]apad[fg];"
            "[bg][fg]amix=inputs=2:duration=first:normalize=0[dub]",
            "-map", "0:v:0", "-map", "[dub]",
        ]
        if keep_original_track:
            args += ["-map", "0:a:0"]
    else:
        args += ["-filter_complex", "[1:a]apad[dub]", "-map", "0:v:0", "-map", "[dub]", "-shortest"]
        keep_original_track = False

    if ru_srt:
        args += ["-map", "2:s:0", "-c:s", "mov_text", "-metadata:s:s:0", "language=rus"]

    args += [
        "-c:v", "copy",
        "-c:a:0", "aac", "-b:a:0", "160k",
        "-metadata:s:a:0", "language=rus", "-metadata:s:a:0", "title=Русский",
        "-disposition:a:0", "default",
    ]
    if keep_original_track:
        args += [
            "-c:a:1", "copy",  # the English original is kept as-is (no re-encoding: faster, no quality loss)
            "-metadata:s:a:1", "language=eng", "-metadata:s:a:1", "title=English (original)",
            "-disposition:a:1", "0",
        ]
    args += ["-movflags", "+faststart", str(out_mp4)]
    run_ffmpeg(args)
    return out_mp4
