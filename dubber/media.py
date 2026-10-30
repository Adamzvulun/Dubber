"""Thin wrappers around the ffmpeg / ffprobe command-line tools."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


class MediaError(RuntimeError):
    pass


def require_ffmpeg() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise MediaError(f"'{tool}' was not found on PATH. Install ffmpeg first (see README).")


def run_ffmpeg(args: list[str]) -> None:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise MediaError(f"ffmpeg failed: {' '.join(cmd)}\n{result.stderr.strip()}")


def probe(path: Path) -> dict:
    cmd = ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise MediaError(f"ffprobe failed on {path}: {result.stderr.strip()}")
    return json.loads(result.stdout)


def duration(path: Path) -> float:
    return float(probe(path)["format"]["duration"])


def video_codec(path: Path) -> str:
    """Codec name of the first video stream ("h264", "hevc", "vp9", "av1"...), "" when there is none."""
    return next((s.get("codec_name", "") for s in probe(path)["streams"] if s.get("codec_type") == "video"), "")


_X264 = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21"]
_NVENC = ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", "23", "-b:v", "0"]  # the NVIDIA card's encoder


def to_h264(src: Path, dst: Path, max_height: int = 720, card: bool | None = None) -> Path:
    """Re-encode the video as H.264 (at most `max_height` high), audio as AAC: the one format every browser,
    Windows player and phone plays. TikTok and iPhones often give HEVC, which many Windows browsers can't show.

    With an NVIDIA card (`card`, default: gpu.has_card()) its own encoder does it, several times faster than the
    processor; an ffmpeg without it, or a card that refuses, → the processor (ADR-045)."""
    if card is None:
        from .gpu import has_card

        card = has_card()
    common = ["-pix_fmt", "yuv420p", "-vf", f"scale=-2:'min({max_height},ih)'", "-c:a", "aac", "-b:a", "160k",
              "-movflags", "+faststart", str(dst)]
    if card:
        try:
            run_ffmpeg(["-i", str(src), "-map", "0:v:0", "-map", "0:a?", *_NVENC, *common])
            return dst
        except MediaError:
            dst.unlink(missing_ok=True)
    run_ffmpeg(["-i", str(src), "-map", "0:v:0", "-map", "0:a?", *_X264, *common])
    return dst


def has_audio(path: Path) -> bool:
    return any(s.get("codec_type") == "audio" for s in probe(path)["streams"])


def extract_audio(video: Path, out_wav: Path, sample_rate: int = 16000) -> Path:
    """Mono 16 kHz WAV — the format Whisper expects."""
    run_ffmpeg(["-i", str(video), "-vn", "-ac", "1", "-ar", str(sample_rate), "-c:a", "pcm_s16le", str(out_wav)])
    return out_wav


def decode_audio(path: Path, sample_rate: int = 24000, audio_filter: str | None = None):
    """Decode any audio file to a mono float32 numpy array (optionally through an ffmpeg filter)."""
    import numpy as np

    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path)]
    if audio_filter:
        cmd += ["-af", audio_filter]
    cmd += ["-ac", "1", "-ar", str(sample_rate), "-f", "f32le", "-"]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise MediaError(f"ffmpeg could not decode {path}: {result.stderr.decode(errors='replace').strip()}")
    return np.frombuffer(result.stdout, dtype=np.float32)


def write_wav(samples, path: Path, sample_rate: int = 24000) -> Path:
    """Write a mono float array (-1..1) as 16-bit PCM WAV."""
    import wave

    import numpy as np

    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm.tobytes())
    return path


def thumbnail(video: Path, out_jpg: Path, width: int = 640) -> Path:
    """A frame from about a third into the video (skips black intros), as JPEG."""
    at = min(30.0, duration(video) / 3)
    run_ffmpeg(
        ["-ss", f"{at:.2f}", "-i", str(video), "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "4", str(out_jpg)]
    )
    return out_jpg
