"""Optional voice — the dub in the original speaker's own voice (OmniVoice), for PCs with an NVIDIA graphics card.

Research and measurements: docs/RESEARCH.md "VoiceStudio / OmniVoice", ADR-028. OmniVoice (k2-fsa; code Apache-2.0,
weights CC-BY-NC = personal use only) copies a voice from a few seconds of speech and can speak a line in a given
number of seconds. Each line copies whoever said it: its reference is the same moment of the original, taken from the
voice track separate.py splits off (so music doesn't leak into the copy). On 4 CPU cores it ran ~20x slower than real
time, so the website offers it only with an NVIDIA card of >= 6 GB. Hebrew is left to Edge: OmniVoice learned 13 h of
it and garbled it when measured.

Not installed with Dubber: PyTorch for CUDA + omnivoice (~3 GB) and the model (~2.4 GB) are installed from the
Settings page (`Installer`); `ready()` says whether that finished.
"""

from __future__ import annotations

import hashlib
import importlib.util
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from . import timing
from .hub import retry
from .media import run_ffmpeg, write_wav
from .segments import Segment
from .tts import speakable

log = logging.getLogger(__name__)

VOICE = "original"  # the website's voice choice next to "male" / "female"
MODEL_REPO = "k2-fsa/OmniVoice"
OMNIVOICE = "omnivoice==0.2.1"  # pinned: the calls below were written against this version
TORCH_INDEX = "https://download.pytorch.org/whl/cu128"  # CUDA 12.8 builds: GeForce 10xx-50xx with a current driver
MIN_VRAM_GB = 6.0  # OmniVoice's measured floor; below it the card swaps to system memory and crawls
UNSUPPORTED = {"he"}  # measured garbled (docs/RESEARCH.md) — these dubs use the Edge voice
LANG_IDS = {"ar": "arb"}  # OmniVoice's ids where they differ from ours
SAMPLE_RATE = 24000
MIN_REF = 3.0  # seconds of the speaker a line's reference should have (OmniVoice: 3-10 s is best)
MAX_REF = 15.0  # longer references are refused by OmniVoice (with a transcript: 20 s)
JOIN_GAP = 1.0  # neighbouring lines join one reference only across pauses this short (likely the same speaker)
LOUDNESS = 0.1  # RMS every clip is brought to (the copied voices are as loud as their references otherwise)
BATCH = 4  # lines per model call on a 6-8 GB card (batch_for): several at once use the graphics card better
# Never ask for a line faster than people speak: told to fit less time, the model swallows and warps the words
# (Adam's dub, 2026-10-29: its own guess was ~0.15 s for whole words, and crowded stretches were planned 1.6x fast).
MAX_SYLLABLES_PER_SECOND = 7.0  # fast but clear speech
LINE_EDGES = 0.2  # seconds a line needs beyond its syllables (onset and release)
# The install's progress bar (Installer.progress): each step's share of the whole and how many bytes it downloads.
STEP_SHARES = {"torch": 0.5, "omnivoice": 0.12, "model": 0.38}
STEP_BYTES = {"torch": 3.4e9, "omnivoice": 0.45e9, "model": 3_267_470_260}  # model: k2-fsa/OmniVoice on Hugging Face
_DOWNLOADING = re.compile(r"Downloading (\S+?)(?: \(([\d.]+) ([kMG]B)\))?\s*$", re.M)
_UNITS = {"kB": 1e3, "MB": 1e6, "GB": 1e9}


def marker() -> Path:
    """Written when the install finished and the graphics card answered (next to the components it installed)."""
    return Path(sys.prefix) / "dubber-omnivoice"


def installed() -> bool:
    return all(importlib.util.find_spec(name) is not None for name in ("torch", "omnivoice"))


def ready() -> bool:
    return marker().is_file() and installed()


def supports(lang: str) -> bool:
    return lang not in UNSUPPORTED


_CYRILLIC_VOWELS = set("аеёиоуыэюяіїє")
_LATIN_VOWEL_RUN = re.compile(r"[aeiouyàáâãäåæèéêëìíîïòóôõöøùúûüýÿœ]+")
_SYLLABLE_SIGNS = re.compile(r"[぀-ヿ一-鿿]")  # kana and Chinese characters: one syllable each
_ARABIC_LETTERS = re.compile(r"[ء-ي]")


def syllables(text: str) -> int:
    """About how many syllables `text` has, in any dub language the original voice speaks."""
    text = text.lower()
    return (sum(ch in _CYRILLIC_VOWELS for ch in text) + len(_LATIN_VOWEL_RUN.findall(text))
            + len(_SYLLABLE_SIGNS.findall(text)) + len(_ARABIC_LETTERS.findall(text)) // 2)  # short vowels unwritten


def min_seconds(text: str) -> float:
    """The shortest time a line can be said in and still be understood."""
    return LINE_EDGES + syllables(text) / MAX_SYLLABLES_PER_SECOND


def batch_for(vram_gb: float) -> int:
    """Lines per model call for a card with this much memory (more at once keeps a big card busy)."""
    return 12 if vram_gb >= 14 else 8 if vram_gb >= 10 else BATCH


def gpu_info(run=subprocess.run) -> dict | None:
    """The NVIDIA card's name and memory in GB, from the driver's nvidia-smi (None: no NVIDIA card or driver)."""
    try:
        result = run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                     capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    cards = []
    for line in result.stdout.strip().splitlines():
        name, _, memory = line.rpartition(",")
        try:
            cards.append({"name": name.strip(), "vram_gb": round(float(memory) / 1024, 1)})
        except ValueError:
            continue
    return max(cards, key=lambda c: c["vram_gb"], default=None)


def status(run=subprocess.run) -> dict:
    gpu = gpu_info(run)
    return {"gpu": gpu, "gpu_ok": bool(gpu and gpu["vram_gb"] >= MIN_VRAM_GB), "installed": installed(),
            "ready": ready(), "min_vram_gb": MIN_VRAM_GB, "unsupported": sorted(UNSUPPORTED),
            "cuda": cuda_status()}


# Does the installed PyTorch really compute on the card? A tiny computation in a separate Python (importing PyTorch
# takes seconds and a lot of memory). Without it OmniVoice silently ran on the processor: ~20x slower than real time.
_CUDA_CHECK = """
import json, torch
ok = torch.cuda.is_available()
if ok:
    (torch.ones(8, device="cuda") * 2).sum().item()  # "no kernel image" (a card newer than this PyTorch) fails here
print(json.dumps({"available": ok, "name": torch.cuda.get_device_name(0) if ok else None,
                  "torch": torch.__version__, "cuda": torch.version.cuda}))
"""
_cuda: dict = {}  # {"result": dict} once checked, {"running": True} while checking; reset after an install
_cuda_lock = threading.Lock()


def _check_cuda(run) -> dict:
    try:
        result = run([sys.executable, "-c", _CUDA_CHECK], capture_output=True, text=True, encoding="utf-8",
                     errors="replace", timeout=180)
        if result.returncode == 0:
            import json

            return json.loads(result.stdout.strip().splitlines()[-1])
        lines = (result.stderr or result.stdout or "").strip().splitlines()
        return {"available": False, "error": lines[-1] if lines else f"exit code {result.returncode}"}
    except (OSError, subprocess.SubprocessError, ValueError, IndexError) as exc:
        return {"available": False, "error": str(exc)}


def cuda_status(run=subprocess.run, wait: bool = False) -> dict | None:
    """{"available", "name", "torch", "cuda"} or {"available": False, "error"}; None while still checking (the
    Settings page asks again) or when the original voice isn't installed. `wait`: check now (the pipeline)."""
    if not installed():
        return None
    with _cuda_lock:
        if "result" in _cuda:
            return _cuda["result"]
        if not wait:
            if not _cuda.get("running"):
                _cuda["running"] = True

                def check() -> None:
                    result = _check_cuda(run)
                    with _cuda_lock:
                        _cuda.update(result=result, running=False)

                threading.Thread(target=check, daemon=True, name="cuda-check").start()
            return None
    result = _check_cuda(run)
    with _cuda_lock:
        _cuda.update(result=result, running=False)
    return result


def cuda_ok(run=subprocess.run) -> bool:
    """The original voice may run: PyTorch computes on the card (or DUBBER_CLONE_DEVICE asks for another device)."""
    if os.environ.get("DUBBER_CLONE_DEVICE"):
        return True
    return bool((cuda_status(run, wait=True) or {}).get("available"))


# Run in a separate Python after installing: the server itself never loads PyTorch until a dub needs it.
_CHECK = f"""
import torch
assert torch.cuda.is_available(), "PyTorch does not see the NVIDIA card (CUDA)"
print(torch.cuda.get_device_name(0), torch.__version__)
from huggingface_hub import snapshot_download
snapshot_download("{MODEL_REPO}")
"""


class Installer:
    """Installs the components in the background, one step at a time; `state` is what the Settings page shows."""

    STEPS = ("torch", "omnivoice", "model")

    def __init__(self, log_file: Path, python: str = sys.executable, run=subprocess.run):
        self.log_file = log_file
        self.python = python
        self.run = run
        self.state: dict = {"running": False, "step": "", "error": "", "done": ready()}
        self._lock = threading.Lock()

    def commands(self) -> list[tuple[str, list[str]]]:
        # --no-cache-dir: no second copy of PyTorch's 3 GB in pip's cache (and the download is a file progress() sees)
        pip = [self.python, "-m", "pip", "install", "--disable-pip-version-check", "--no-cache-dir",
               "--log", str(self.log_file)]
        return [
            ("torch", pip + ["torch", "torchaudio", "--index-url", TORCH_INDEX]),
            ("omnivoice", pip + [OMNIVOICE]),  # keeps the CUDA PyTorch: omnivoice asks for any version
            ("model", [self.python, "-c", _CHECK]),
        ]

    def progress(self, temp_dir: Path | None = None, hub_dir: Path | None = None) -> float | None:
        """0..1 of the whole install while it runs (None otherwise), from the bytes downloaded so far: pip's
        downloads announced in the log and their growing files in pip's temp folders; the model's files in the
        Hugging Face cache. Never quite 1 before the install says it is done (unpacking takes a while too)."""
        step = self.state.get("step")
        if not self.state.get("running") or step not in STEP_SHARES:
            return None
        done = sum(STEP_SHARES[s] for s in STEP_SHARES if list(STEP_SHARES).index(s) < list(STEP_SHARES).index(step))
        if step == "model":
            got = _folder_bytes((hub_dir or _hub_cache()) / ("models--" + MODEL_REPO.replace("/", "--")))
        else:
            got = self._pip_bytes(step, temp_dir or Path(tempfile.gettempdir()))
        return round(done + STEP_SHARES[step] * min(0.97, got / STEP_BYTES[step]), 3)

    def _pip_bytes(self, step: str, temp_dir: Path) -> float:
        """Bytes pip downloaded in this step: finished downloads (sizes from the log) + the one in progress."""
        try:
            log_text = self.log_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return 0.0
        start = log_text.rfind(f" {step}: ")  # this step's header line (written by _install)
        log_text = log_text[start:] if start >= 0 else ""
        found = [(urllib.parse.unquote(name.rsplit("/", 1)[-1]), float(size or 0) * _UNITS.get(unit, 0))
                 for name, size, unit in _DOWNLOADING.findall(log_text) if not name.endswith(".metadata")]
        if not found:
            return 0.0
        finished = sum(size for _, size in found[:-1])
        partial = max((f.stat().st_size for f in temp_dir.glob(f"pip-unpack-*/{found[-1][0]}") if f.is_file()),
                      default=0)
        return finished + (partial or 0)

    def start(self) -> bool:
        """Start installing (False when it is already running)."""
        if not self._lock.acquire(blocking=False):
            return False
        self.state.update(running=True, step="", error="", done=False)
        threading.Thread(target=self._install, daemon=True).start()
        return True

    def _install(self) -> None:
        try:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            for step, cmd in self.commands():
                self.state["step"] = step
                with self.log_file.open("a", encoding="utf-8") as out:
                    out.write(f"\n== {time.strftime('%Y-%m-%d %H:%M:%S')} {step}: {' '.join(cmd[:6])} ...\n")
                    out.flush()
                    result = self.run(cmd, stdout=out, stderr=subprocess.STDOUT)
                if result.returncode != 0:
                    self.state["error"] = step
                    return
            importlib.invalidate_caches()  # the server may now find the new packages
            marker().write_text(time.strftime("%Y-%m-%dT%H:%M:%S"), encoding="utf-8")
            with _cuda_lock:
                _cuda.clear()  # a new PyTorch: check the card again
            self.state["done"] = True
        except OSError as exc:  # e.g. the disk is full
            log.warning("Installing the original voice failed: %s", exc)
            self.state["error"] = self.state["step"] or "torch"
        finally:
            self.state["running"] = False
            self._lock.release()


def _hub_cache() -> Path:
    from huggingface_hub import constants

    return Path(constants.HF_HUB_CACHE)


def _folder_bytes(folder: Path) -> int:
    return sum(f.stat().st_size for f in folder.rglob("*") if f.is_file() and not f.is_symlink()) \
        if folder.is_dir() else 0


class Engine(Protocol):
    """What the dub needs from the voice model (OmniVoiceEngine; tests use a stand-in)."""

    def prompt(self, audio, text: str) -> object: ...
    def natural_seconds(self, text: str, prompt: object) -> float: ...
    def speak(self, texts: list[str], prompts: list[object], durations: list[float], lang: str) -> list: ...
    def close(self) -> None: ...


class OmniVoiceEngine:
    def __init__(self, device: str | None = None):
        import torch
        from omnivoice import OmniVoice

        self.torch = torch
        device = device or os.environ.get("DUBBER_CLONE_DEVICE") or ("cuda" if torch.cuda.is_available() else "cpu")
        dtype = torch.float16 if device.startswith("cuda") else torch.float32
        self.device = torch.cuda.get_device_name(0) if device.startswith("cuda") else device
        self.batch = batch_for(torch.cuda.get_device_properties(0).total_memory / 2**30) \
            if device.startswith("cuda") else BATCH
        self.model = retry(lambda: OmniVoice.from_pretrained(MODEL_REPO, device_map=device, dtype=dtype))

    def prompt(self, audio, text: str) -> object:
        return self.model.create_voice_clone_prompt(ref_audio=(self.torch.from_numpy(audio)[None], SAMPLE_RATE),
                                                    ref_text=text)

    def natural_seconds(self, text: str, prompt) -> float:
        # The model's own estimate: the line at the reference's speaking speed. Without its boost for short lines
        # (low_threshold): that made "Прекрасно." 1.3 s instead of 0.5 s, so the planned pace of the whole video
        # came out ~1.5x too fast and the dub ended long before the speaker (measured, docs/RESEARCH.md).
        tokens = self.model.duration_estimator.estimate_duration(text, prompt.ref_text,
                                                                 prompt.ref_audio_tokens.size(-1), low_threshold=None)
        return tokens / self.model.audio_tokenizer.config.frame_rate

    def speak(self, texts, prompts, durations, lang):
        import numpy as np

        try:
            out = self.model.generate(text=texts, language=LANG_IDS.get(lang, lang), voice_clone_prompt=prompts,
                                      duration=durations)
        except self.torch.cuda.OutOfMemoryError:
            self.torch.cuda.empty_cache()  # free what the failed call held before a smaller group is tried
            raise
        return [np.asarray(a, dtype=np.float32).reshape(-1) for a in out]

    def close(self) -> None:
        del self.model
        if self.torch.cuda.is_available():
            self.torch.cuda.empty_cache()


def reference_lines(segments: list[Segment], i: int) -> list[int]:
    """The lines whose audio is line i's voice reference: the line itself, joined with neighbours while it is shorter
    than MIN_REF — only across short pauses, so it is most likely still the same speaker.

    A line longer than MAX_REF borrows the nearest line that fits (OmniVoice refuses long references).
    """
    if segments[i].duration > MAX_REF:
        fits = [j for j, s in enumerate(segments) if 1.0 <= s.duration <= MAX_REF]
        if not fits:
            return []
        i = min(fits, key=lambda j: abs(segments[j].start - segments[i].start))
    lo = hi = i
    while segments[hi].end - segments[lo].start < MIN_REF:
        before = segments[lo].start - segments[lo - 1].end if lo > 0 else None
        after = segments[hi + 1].start - segments[hi].end if hi + 1 < len(segments) else None
        options = [(gap, side) for gap, side in ((before, -1), (after, 1)) if gap is not None and gap <= JOIN_GAP]
        if not options:
            break
        _, side = min(options)
        new_lo, new_hi = (lo - 1, hi) if side < 0 else (lo, hi + 1)
        if segments[new_hi].end - segments[new_lo].start > MAX_REF:
            break
        lo, hi = new_lo, new_hi
    return list(range(lo, hi + 1))


class VoiceTrack:
    """The separated voice of the whole video at 24 kHz mono, read from disk one reference at a time."""

    def __init__(self, vocals_wav: Path, work: Path):
        import numpy as np

        raw = work / "vocals_24k.f32"
        if not raw.exists():
            partial = raw.with_suffix(".partial")
            run_ffmpeg(["-i", str(vocals_wav), "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", str(partial)])
            partial.replace(raw)
        self.audio = np.memmap(raw, dtype=np.float32, mode="r")

    def cut(self, start: float, end: float):
        import numpy as np

        a, b = max(0, int((start - 0.05) * SAMPLE_RATE)), int((end + 0.05) * SAMPLE_RATE)
        return np.array(self.audio[a:b], dtype=np.float32)

    def close(self) -> None:
        self.audio = None  # Windows can't delete a file that is still mapped


def _level(audio):
    import numpy as np

    rms = float(np.sqrt(np.mean(audio * audio))) if len(audio) else 0.0
    if rms < 1e-4:
        return audio
    audio = audio * (LOUDNESS / rms)
    peak = float(np.abs(audio).max())
    return audio * (0.95 / peak) if peak > 0.95 else audio


def synthesize(
    segments: list[Segment],
    vocals_wav: Path,
    lang: str,
    clips_dir: Path,
    max_speedup: float,
    engine: Engine | None = None,
    progress: Callable[[float], None] | None = None,
    batch: int | None = None,
) -> tuple[list[Path | None], list[float]]:
    """Speak every line in the voice of whoever said it; returns one clip per line (None = nothing to say) and the
    speaking-rate factors asked for (for timing.json).

    Like the Edge voice, the pace follows the speaker (timing.plan_rates), but instead of asking for a rate the model
    is told each line's length — never less than `min_seconds` (a line that then runs long pushes the next one back,
    align.py). Lines of similar length share a model call (`batch` lines, default: what the card's memory allows).
    Finished clips are reused; `progress` may raise to cancel between model calls.
    """
    clips_dir.mkdir(parents=True, exist_ok=True)
    voice = VoiceTrack(vocals_wav, clips_dir.parent)
    own = engine is None
    engine = engine or OmniVoiceEngine()
    try:
        todo = [i for i, s in enumerate(segments) if speakable(s.ru)]
        refs = {i: reference_lines(segments, i) for i in todo}
        prompts: dict[tuple, object] = {}
        for i in todo:
            key = tuple(refs[i])
            if key and key not in prompts:
                first, last = segments[key[0]], segments[key[-1]]
                text = " ".join(segments[j].text.strip() for j in key)
                prompts[key] = engine.prompt(voice.cut(first.start, last.end), text)
        if todo and not prompts:
            raise RuntimeError("No line of this video is short enough to copy the voice from")
        fallback = next(iter(prompts.values()), None)

        def prompt_for(i: int) -> object:
            return prompts.get(tuple(refs[i]), fallback)

        natural: list[float | None] = [None] * len(segments)
        for i in todo:
            natural[i] = engine.natural_seconds(segments[i].ru, prompt_for(i))
        rates = timing.plan_rates(segments, natural, max_speedup)

        clips: list[Path | None] = [None] * len(segments)
        missing = []
        for i in todo:
            seconds = round(max(natural[i] / rates[i], min_seconds(segments[i].ru)), 2)
            rates[i] = natural[i] / seconds
            digest = hashlib.sha1(f"{segments[i].ru}|{lang}|{refs[i]}|{seconds}".encode()).hexdigest()[:10]
            clips[i] = clips_dir / f"{i:05d}_{digest}.wav"
            if not (clips[i].exists() and clips[i].stat().st_size > 0):
                missing.append((i, seconds))
        # Longest first: lines of similar length share a call (no card time spent on padding short ones), and a
        # group too big for the card's memory shows up at once.
        missing.sort(key=lambda item: -item[1])
        batch = batch or getattr(engine, "batch", BATCH)
        # In the program's window: where the voice runs and how fast (Adam's 90-minute estimate, 2026-10-29).
        where = getattr(engine, "device", "")
        if missing:
            print(f"Голос оригинала: {len(missing)} строк, {where or 'устройство не известно'}, по {batch} за раз",
                  flush=True)
        began, done = time.monotonic(), 0
        while done < len(missing):
            group = missing[done:done + batch]
            tick = time.monotonic()
            texts, group_prompts = [segments[i].ru for i, _ in group], [prompt_for(i) for i, _ in group]
            try:
                audios = engine.speak(texts, group_prompts, [s for _, s in group], lang)
            except Exception:
                if len(group) == 1:
                    raise
                # e.g. the card ran out of memory with several long lines at once: half as many from now on
                batch = max(1, len(group) // 2)
                log.warning("The original voice: %d lines at once failed; trying %d", len(group), batch)
                continue
            for (i, _), audio in zip(group, audios, strict=True):
                write_wav(_level(audio), clips[i], SAMPLE_RATE)
            done += len(group)
            print(f"Голос оригинала: {done}/{len(missing)} строк, {time.monotonic() - tick:.1f} с на группу, "
                  f"всего {time.monotonic() - began:.0f} с", flush=True)
            if progress:
                progress(done / len(missing))
        return clips, rates
    finally:
        voice.close()
        if own:
            engine.close()
