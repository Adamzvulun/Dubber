"""Optional stage — the original soundtrack without the speaker's voice (music and sounds stay), for under the dub.

Uses Demucs v4 (`htdemucs`, Meta's voice/music separation model) exported to ONNX, so it runs on the CPU with
onnxruntime — no PyTorch. The model splits audio into drums, bass, other and vocals; the background is everything but
the vocals. Audio is processed in 7.8-s windows with a quarter overlap (cross-faded), read from and written to files
on disk, so a long video never has to fit in memory.

On an NVIDIA PC whose card libraries gpu.py installed (ADR-045), the same work runs on the card in a child process
that loads onnxruntime-gpu from its own folder (`gpu.ORT_DIR`); if that fails, it runs here on the processor.
"""

from __future__ import annotations

import collections
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from . import gpu
from .hub import retry
from .media import MediaError, run_ffmpeg

log = logging.getLogger(__name__)

MODEL_REPO = "StemSplitio/htdemucs-onnx"  # MIT; parity with the PyTorch model checked by its authors (≤7e-4)
MODEL_FILE = "htdemucs_fp16weights.onnx"  # 166 MB (fp16-stored weights, same results as the 316 MB fp32 file)
SAMPLE_RATE = 44100
WINDOW = int(7.8 * SAMPLE_RATE)  # the length the model was exported for
OVERLAP = WINDOW // 4
VOCALS = 3  # stem order in the model's output: drums, bass, other, vocals

# (input of shape (1, 2, WINDOW)) -> stems of shape (1, 4, 2, WINDOW)
SeparateFn = Callable[["object"], "object"]


_gpu_failed = False  # the card failed once in this run of the program: the processor from now on


def load_model(card: bool = False) -> SeparateFn:
    import onnxruntime as ort
    from huggingface_hub import hf_hub_download

    path = retry(lambda: hf_hub_download(MODEL_REPO, MODEL_FILE))  # downloaded once, then cached
    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"] if card else ["CPUExecutionProvider"]
    session = ort.InferenceSession(path, sess_options=options, providers=providers)
    if card and session.get_providers()[0] != "CUDAExecutionProvider":  # onnxruntime fell back to the processor
        raise RuntimeError(f"The graphics card is not used: {session.get_providers()}")
    return lambda mix: session.run(["stems"], {"mix": mix})[0]


_CHILD = """
import sys
sys.path.insert(0, sys.argv[1])  # onnxruntime-gpu, not the program's own onnxruntime
import onnxruntime
if hasattr(onnxruntime, "preload_dlls"):
    onnxruntime.preload_dlls()  # its CUDA libraries, installed next to it
from pathlib import Path
from dubber import separate
video, out, vocals = sys.argv[2], sys.argv[3], sys.argv[4]
separate.separate_background(Path(video), Path(out), model=separate.load_model(card=True),
                             progress=lambda f: print(f"progress {f:.4f}", flush=True),
                             vocals_wav=Path(vocals) if vocals else None)
"""


def on_card(video: Path, out_wav: Path, progress, vocals_wav: Path | None, python: str = sys.executable,
            ort_dir: Path | None = None) -> bool:
    """`separate_background` on the graphics card, in a child process (gpu.py); False when it didn't work there.
    `progress` raising (a cancelled job) stops the child and raises on."""
    cmd = [python, "-c", _CHILD, str(ort_dir or gpu.ORT_DIR), str(video), str(out_wav), str(vocals_wav or "")]
    child = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                             errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    said = collections.deque(maxlen=20)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    before = set(out_wav.parent.glob("tmp*"))  # the child's work folder: removed here if the child is stopped
    try:
        for line in child.stdout:
            if line.startswith("progress ") and progress:
                progress(float(line.split()[1]))
            elif line.strip():
                said.append(line.rstrip())
        code = child.wait()
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()
            for left in set(out_wav.parent.glob("tmp*")) - before:
                shutil.rmtree(left, ignore_errors=True)
    if code != 0:
        log.warning("Voice removal on the graphics card failed (%s):\n%s", code, "\n".join(said))
    return code == 0


def _loudness(mix, block: int = 10 * SAMPLE_RATE) -> tuple[float, float]:
    """Mean and standard deviation of the mono mix, read in blocks (a long video never sits in memory at once).
    Demucs scales its input to unit loudness and back (as demucs.separate does)."""
    total = mix.shape[1]
    s1 = s2 = 0.0
    for i in range(0, total, block):
        mono = mix[:, i:i + block].mean(axis=0, dtype="float64")
        s1, s2 = s1 + float(mono.sum()), s2 + float((mono * mono).sum())
    mean = s1 / total
    return mean, (max(s2 / total - mean * mean, 0.0) ** 0.5) or 1.0


def separate_background(
    video: Path, out_wav: Path, model: SeparateFn | None = None, progress: Callable[[float], None] | None = None,
    vocals_wav: Path | None = None,
) -> Path:
    """Write the background (the original audio minus the voice) of `video` to `out_wav` (44.1 kHz stereo).

    With `vocals_wav`, the voice alone is written there too (the references for the original-voice dub, clone.py).
    `progress(fraction)` is called after every window; raising from it stops the work (used to cancel a job).
    Finished files are reused; a half-written one is never left behind.
    """
    import numpy as np

    global _gpu_failed
    wanted = [out_wav] + ([vocals_wav] if vocals_wav else [])
    if all(f.exists() and f.stat().st_size > 0 for f in wanted):
        return out_wav
    if model is None and not _gpu_failed and gpu.ort_ready():
        print("Отделяю голос на видеокарте", flush=True)
        if on_card(video, out_wav, progress, vocals_wav):
            return out_wav
        _gpu_failed = True
        print("Видеокарта не справилась — отделяю голос на процессоре (медленнее).", flush=True)
    model = model or load_model()
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out_wav.parent, ignore_cleanup_errors=True) as tmp:
        raw_in, raw_out, raw_voice = Path(tmp) / "mix.f32", Path(tmp) / "background.f32", Path(tmp) / "vocals.f32"
        run_ffmpeg(["-i", str(video), "-vn", "-ac", "2", "-ar", str(SAMPLE_RATE), "-f", "f32le", str(raw_in)])
        if raw_in.stat().st_size == 0:
            raise MediaError(f"No audio in {video}")
        mix = out = voice = None
        try:
            mix = np.memmap(raw_in, dtype=np.float32, mode="r").reshape(-1, 2).T  # (2, samples)
            total = mix.shape[1]
            out = np.memmap(raw_out, dtype=np.float32, mode="w+", shape=(total, 2)).T
            if vocals_wav:
                voice = np.memmap(raw_voice, dtype=np.float32, mode="w+", shape=(total, 2)).T
            mean, std = _loudness(mix)
            ramp = np.linspace(0, 1, OVERLAP, dtype=np.float32)
            stride = WINDOW - OVERLAP
            windows = max(1, -(-max(total - OVERLAP, 1) // stride))
            for i in range(windows):
                start = i * stride
                end = min(start + WINDOW, total)
                chunk = np.zeros((1, 2, WINDOW), dtype=np.float32)
                chunk[0, :, : end - start] = (mix[:, start:end] - mean) / std
                stems = model(chunk)[0]  # (4, 2, WINDOW)
                background = stems[:VOCALS].sum(axis=0)[:, : end - start] * std + mean
                # Cross-fade with the neighbours: the two ramps of an overlap add up to exactly 1.
                w = np.ones(end - start, dtype=np.float32)
                if start > 0:
                    w[:OVERLAP] = ramp
                if end < total:
                    w[-OVERLAP:] = ramp[::-1]
                out[:, start:end] += background * w
                if voice is not None:
                    voice[:, start:end] += stems[VOCALS][:, : end - start] * std * w
                if progress:
                    progress((i + 1) / windows)
            out.flush()
            if voice is not None:
                voice.flush()
        finally:
            mix = out = voice = None  # close the memory-mapped files (Windows can't delete open ones)
        for raw, wav in ((raw_out, out_wav), (raw_voice, vocals_wav)):
            if wav is None:
                continue
            partial = wav.with_name(wav.stem + ".partial.wav")
            run_ffmpeg(["-f", "f32le", "-ar", str(SAMPLE_RATE), "-ac", "2", "-i", str(raw),
                        "-c:a", "pcm_s16le", str(partial)])
            partial.replace(wav)
    return out_wav

