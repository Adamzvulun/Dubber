"""Optional voice — the dub in the original speaker's own voice (OmniVoice), for PCs with an NVIDIA graphics card.

Research and measurements: docs/RESEARCH.md "VoiceStudio / OmniVoice", ADR-028. OmniVoice (k2-fsa; code Apache-2.0,
weights CC-BY-NC = personal use only) copies a voice from a few seconds of speech and can speak a line in a given
number of seconds. Each line copies whoever said it: its reference is the same moment of the original, taken from the
voice track separate.py splits off (so music doesn't leak into the copy). On 4 CPU cores it ran ~20x slower than real
time, so the website offers it only with an NVIDIA card of >= 6 GB. Hebrew is left to Edge: OmniVoice learned 13 h of
it and garbled it when measured.

Not installed with Dubber: PyTorch for CUDA + omnivoice (~3 GB) and the model (~2.4 GB) are installed from the
Settings page (`Installer`); `ready()` says whether that finished. The voice converter that takes the English accent
out of a line (`VoiceConverter`, ADR-043: ~0.2 GB of packages + a 1 GB model) is part of that install; PCs that
installed the original voice before it get it in the background at start (`converter_missing`).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
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
from difflib import SequenceMatcher
from pathlib import Path
from typing import Protocol

from . import timing
from .hub import retry
from .media import decode_audio, run_ffmpeg, write_wav
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
IDEAL_REF = 10.0  # seconds: a speaker's reference is made as long as this when they have that much in one go
LOUDNESS = 0.1  # RMS every clip is brought to (the copied voices are as loud as their references otherwise)
BATCH = 4  # lines per model call on a 6-8 GB card (batch_for): several at once use the graphics card better
# Never ask for a line faster than people speak: told to fit less time, the model swallows and warps the words
# (Adam's dub, 2026-10-29: its own guess was ~0.15 s for whole words, and crowded stretches were planned 1.6x fast).
MAX_SYLLABLES_PER_SECOND = 7.0  # fast but clear speech
LINE_EDGES = 0.2  # seconds a line needs beyond its syllables (onset and release)
# Measured on the real model (docs/RESEARCH.md, session 9): at its own pace every test line came out whole, but asked
# for only 7% less time one line was garbled ("Кей, ты видел…" -> "КТ-Виддл. Стон…") — the model samples, so slips
# are partly random. So the copied voice is hurried less than Edge's, and every new clip is listened to (Whisper):
MAX_RATE = 1.25  # at most this much faster than the voice's own pace
TRIES = 3  # a line whose words can't be heard is spoken again; the last try at the voice's own pace
HEARD_ENOUGH = 0.8  # share of a line's words the listener must hear
# The accent (ADR-043, docs/RESEARCH.md "The English accent…"): OmniVoice speaks with the accent of the speech it copies
# the voice from. The listener also says how sure it is that a clip is in the dub language; a line it doubts is spoken
# again from a native speaker's sample (an Edge voice: `native`) and turned into the speaker's voice by a voice
# converter, which keeps the pronunciation. Kept only when it is as clear and sounds more native.
ACCENT_SURE = 0.9  # measured: accented lines 0.43-0.87, native ones 0.97-1.0
ACCENT_MIN_SECONDS = 1.0  # Whisper's language guess on shorter clips is unreliable
MALE_BELOW_HZ = 165.0  # the speaker's median pitch: which native voice (male/female) the line is spoken from
CONVERTER_REPO, CONVERTER_FILE = "ResembleAI/chatterbox", "s3gen.safetensors"  # Chatterbox's converter (MIT)
# --no-deps: chatterbox-tts pins PyTorch 2.6, which has no build for the newest cards; the converter runs on any recent
# PyTorch (tried with 2.15). Their own dependencies are installed separately.
CONVERTER_PACKAGES = ["chatterbox-tts==0.1.7", "conformer==0.3.2", "s3tokenizer==0.3.0"]
CONVERTER_DEPS = ["diffusers", "einops", "omegaconf", "onnx", "librosa"]
CONVERTER_STEPS = ("converter", "model")  # what a PC that installed the original voice before 0.12.0 still needs
SAME_WORD = 0.85  # similarity at which a heard word counts as the written one (Whisper slips on lone short words)
# The install's progress bar (Installer.progress): each step's share of the whole and how many bytes it downloads.
STEP_SHARES = {"torch": 0.42, "omnivoice": 0.1, "converter": 0.04, "model": 0.44}
# model: k2-fsa/OmniVoice + the converter's s3gen.safetensors on Hugging Face
STEP_BYTES = {"torch": 3.4e9, "omnivoice": 0.45e9, "converter": 0.15e9, "model": 3_267_470_260 + 1_056_484_620}
_DOWNLOADING = re.compile(r"Downloading (\S+?)(?: \(([\d.]+) ([kMG]B)\))?\s*$", re.M)
_UNITS = {"kB": 1e3, "MB": 1e6, "GB": 1e9}


def marker() -> Path:
    """Written when the install finished and the graphics card answered (next to the components it installed)."""
    return Path(sys.prefix) / "dubber-omnivoice"


def installed() -> bool:
    return all(importlib.util.find_spec(name) is not None for name in ("torch", "omnivoice"))


def converter_ready() -> bool:
    """The accent converter's packages are installed (its model downloads with the install's last step)."""
    return all(importlib.util.find_spec(name) is not None for name in ("chatterbox", "s3tokenizer", "diffusers"))


def converter_missing() -> bool:
    """The original voice was installed before the converter existed: fetch it (Installer.start(CONVERTER_STEPS))."""
    return ready() and not converter_ready()


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


def _words(text: str) -> list[str]:
    words = []
    for word in re.findall(r"[^\W\d_]+", text.lower().replace("ё", "е")):
        words += list(word) if _SYLLABLE_SIGNS.fullmatch(word[0]) else [word]  # no spaces in Chinese/Japanese
    return words


def heard_share(text: str, heard: str) -> float:
    """How well a listener's `heard` matches `text`, forgiving small slips: the share of the words that were heard,
    or lower when much was heard that isn't in the text (e.g. an English word in the copied voice)."""
    want, got = _words(text), _words(heard)
    if not want:
        return 1.0
    heard_words, found = len(got), 0
    for word in want:
        best = max(got, key=lambda g: SequenceMatcher(None, word, g).ratio(), default=None)
        if best is not None and SequenceMatcher(None, word, best).ratio() >= SAME_WORD:
            found += 1
            got.remove(best)
    return min(found / len(want), found / heard_words if heard_words else 0.0)


CHECK_FILE = "check.json"


def check_report(clips_dir: Path) -> dict:
    """What the listen-back check heard per line ({"<line>": {"heard", "share", "tries"}})."""
    try:
        return json.loads((clips_dir / CHECK_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


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
from huggingface_hub import hf_hub_download
hf_hub_download("{CONVERTER_REPO}", "{CONVERTER_FILE}")
"""


class Installer:
    """Installs the components in the background, one step at a time; `state` is what the Settings page shows."""

    STEPS = ("torch", "omnivoice", "converter", "model")

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
            ("converter", pip + CONVERTER_DEPS),
            ("converter", pip + ["--no-deps"] + CONVERTER_PACKAGES),
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
            hub = hub_dir or _hub_cache()
            got = sum(_folder_bytes(hub / ("models--" + repo.replace("/", "--")))
                      for repo in (MODEL_REPO, CONVERTER_REPO))
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

    def start(self, steps: tuple[str, ...] | None = None) -> bool:
        """Start installing (False when it is already running); `steps`: only these (e.g. CONVERTER_STEPS)."""
        if not self._lock.acquire(blocking=False):
            return False
        self.state.update(running=True, step="", error="", done=False)
        threading.Thread(target=self._install, args=(steps,), daemon=True).start()
        return True

    def _install(self, steps: tuple[str, ...] | None = None) -> None:
        try:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            for step, cmd in self.commands():
                if steps and step not in steps:
                    continue
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


def _s3gen_class():
    """Chatterbox's converter model, without running the package's __init__ (it loads its text-to-speech models and
    their pinned dependencies, which the converter doesn't need)."""
    import types

    if "chatterbox" not in sys.modules:
        spec = importlib.util.find_spec("chatterbox")
        package = types.ModuleType("chatterbox")
        package.__path__ = list(spec.submodule_search_locations)
        sys.modules["chatterbox"] = package
    from chatterbox.models.s3gen import S3Gen

    return S3Gen


class VoiceConverter:
    """`convert(audio, voice, key)`: the same speech (words, pronunciation, timing) in the voice of `voice` (both
    24 kHz); `key` names the voice, so its sample is analysed once."""

    def __init__(self, device: str | None = None):
        import torch
        from huggingface_hub import hf_hub_download
        from safetensors.torch import load_file

        self.torch = torch
        self.device = (device or os.environ.get("DUBBER_CLONE_DEVICE")
                       or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.model = _s3gen_class()()
        self.model.load_state_dict(load_file(retry(lambda: hf_hub_download(CONVERTER_REPO, CONVERTER_FILE))),
                                   strict=False)
        self.model.to(self.device).eval()
        self.voices: dict = {}

    def __call__(self, audio, voice, key):
        import torchaudio

        torch = self.torch
        with torch.inference_mode():
            if key not in self.voices:
                self.voices[key] = self.model.embed_ref(torch.from_numpy(voice[:10 * SAMPLE_RATE]).float(),
                                                        SAMPLE_RATE, device=self.device)
            speech = torchaudio.functional.resample(torch.from_numpy(audio).float(), SAMPLE_RATE, 16000)
            tokens, _ = self.model.tokenizer(speech[None].to(self.device))
            out, _ = self.model.inference(speech_tokens=tokens, ref_dict=self.voices[key])
        return out.squeeze(0).float().cpu().numpy()

    def close(self) -> None:
        del self.model
        if self.torch.cuda.is_available():
            self.torch.cuda.empty_cache()


def pitch_hz(audio) -> float:
    """The median pitch of voiced speech (autocorrelation per 40-ms frame); 0 when none is found."""
    import numpy as np

    frame, hop = int(0.04 * SAMPLE_RATE), int(0.01 * SAMPLE_RATE)
    lo, hi = SAMPLE_RATE // 400, SAMPLE_RATE // 60
    loud = float(np.sqrt(np.mean(audio * audio))) if len(audio) else 0.0
    found = []
    for start in range(0, len(audio) - frame, hop):
        x = audio[start:start + frame]
        if float(np.sqrt(np.mean(x * x))) < loud:  # quieter than average: pauses and breath
            continue
        x = x - x.mean()
        corr = np.correlate(x, x, "full")[frame - 1:]
        if corr[0] <= 0:
            continue
        lag = lo + int(np.argmax(corr[lo:hi]))
        if corr[lag] / corr[0] > 0.5:  # clearly periodic: voiced
            found.append(SAMPLE_RATE / lag)
    return float(np.median(found)) if found else 0.0


def native_text(segments: list[Segment], todo: list[int], chars: int = 160) -> str:
    """What the native voice says for its sample: the dub's own first lines, about 8-10 s of speech."""
    text = ""
    for i in todo:
        if len(text) >= chars:
            break
        text = f"{text} {segments[i].ru.strip()}".strip()
    return text


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


def speaker_references(segments: list[Segment], speakers: list[int | None]) -> dict[int, list[int]]:
    """One reference per speaker (speakers.py): their longest run of consecutive lines (pauses <= JOIN_GAP), up to
    IDEAL_REF seconds — so every line of a person sounds like the same person, not like whatever 1-3 s were around it.
    A speaker with less than a second of speech in one go gets none (their lines use `reference_lines`)."""
    best: dict[int, tuple[tuple[float, float], list[int]]] = {}
    for lo in range(len(segments)):
        who = speakers[lo]
        if who is None or segments[lo].duration > MAX_REF:
            continue
        hi = lo
        while True:
            total = segments[hi].end - segments[lo].start
            if total > MAX_REF:
                break
            score = (min(total, IDEAL_REF), -total)  # long enough, then the shortest such
            if total >= 1.0 and (who not in best or score > best[who][0]):
                best[who] = (score, list(range(lo, hi + 1)))
            nxt = hi + 1
            if (nxt >= len(segments) or speakers[nxt] != who or segments[nxt].duration > MAX_REF
                    or segments[nxt].start - segments[hi].end > JOIN_GAP):
                break
            hi = nxt
    return {who: lines for who, (_, lines) in best.items()}


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


def _fix_accents(lines, segments, lang, clips, clips_dir, asked, best, report, engine, listen, native, converter,
                 keys, samples, batch) -> None:
    """Speak the accented `lines` again from a native speaker's sample (same text and length), convert each into its
    speaker's voice (`samples[keys[i]]`), listen again, and keep it only when it is as clear and sounds more native.
    Without the converter or the native voice (e.g. no internet for Edge) the lines just keep their accent."""
    print(f"Голос оригинала: в {len(lines)} строках слышен акцент — озвучиваю их с правильным произношением",
          flush=True)
    if native is None or converter is None or not converter_ready():
        print("Голос оригинала: исправление акцента ещё не установлено — строки остаются как есть", flush=True)
        return
    try:
        convert = converter()
    except Exception:
        log.exception("The accent converter failed to load")
        return
    try:
        sex = {key: "male" if 0 < pitch_hz(samples[key]) < MALE_BELOW_HZ else "female" for key in set(keys.values())}
        text = native_text(segments, [i for i, s in enumerate(segments) if speakable(s.ru)])
        prompts = {}
        for gender in sorted(set(sex.values())):
            path = clips_dir / f"native_{gender}.mp3"
            try:
                if not (path.exists() and path.stat().st_size > 0):
                    native(text, gender, path)
                prompts[gender] = engine.prompt(decode_audio(path, SAMPLE_RATE), text)
            except Exception:
                log.exception("The native voice for the accent fix failed")
        fixed = 0
        todo = [i for i in lines if sex[keys[i]] in prompts]
        for n in range(0, len(todo), batch):
            group = todo[n:n + batch]
            audios = engine.speak([segments[i].ru for i in group], [prompts[sex[keys[i]]] for i in group],
                                  [asked[i] for i in group], lang)
            for i, audio in zip(group, audios, strict=True):
                trial = clips[i].with_suffix(".accent.wav")
                write_wav(_level(convert(_level(audio), samples[keys[i]], keys[i])), trial, SAMPLE_RATE)
                heard = listen(trial, lang)
                share, sounds = heard_share(segments[i].ru, heard), getattr(heard, "native", 1.0)
                before = report[str(i)]["native"]
                keep = share >= min(best[i], HEARD_ENOUGH) and sounds > before
                report[str(i)]["accent"] = {"heard": heard, "share": round(share, 2), "native": round(sounds, 2),
                                            "kept": keep}
                if keep:
                    trial.replace(clips[i])
                    fixed += 1
                else:
                    trial.unlink()
        print(f"Голос оригинала: акцент исправлен в {fixed} из {len(lines)} строк", flush=True)
    finally:
        close = getattr(convert, "close", None)
        if close:
            close()


def synthesize(
    segments: list[Segment],
    vocals_wav: Path,
    lang: str,
    clips_dir: Path,
    max_speedup: float,
    engine: Engine | None = None,
    progress: Callable[[float], None] | None = None,
    batch: int | None = None,
    listen: Callable[[Path, str], str] | None = None,
    speakers: list[int | None] | None = None,
    native: Callable[[str, str, Path], None] | None = None,
    converter: Callable[[], Callable] | None = None,
) -> tuple[list[Path | None], list[float]]:
    """Speak every line in the voice of whoever said it; returns one clip per line (None = nothing to say) and the
    speaking-rate factors asked for (for timing.json).

    Like the Edge voice, the pace follows the speaker (timing.plan_rates, at most MAX_RATE), but instead of asking for
    a rate the model is told each line's length — never less than `min_seconds` (a line that then runs long pushes the
    next one back, align.py). Lines of similar length share a model call (`batch` lines, default: what the card's
    memory allows). `listen(clip, lang)` -> the words heard: a line whose words aren't heard is spoken again (TRIES,
    the last at the voice's own pace) and the best try kept; `check_report` says what was heard. `speakers` (who says
    each line, speakers.py): each speaker's lines copy one longer sample of them (`speaker_references`).
    A line `listen` hears with an accent (its `.native` < ACCENT_SURE) is spoken again from a native sample —
    `native(text, "male" | "female", path)` writes one — and turned into the speaker's voice by `converter()`
    (VoiceConverter); see `_fix_accents`. Finished clips are reused; `progress` may raise to cancel between model calls.
    """
    clips_dir.mkdir(parents=True, exist_ok=True)
    voice = VoiceTrack(vocals_wav, clips_dir.parent)
    own = engine is None
    engine = engine or OmniVoiceEngine()
    try:
        todo = [i for i, s in enumerate(segments) if speakable(s.ru)]
        own_refs = speaker_references(segments, speakers) if speakers else {}
        refs = {i: own_refs.get(speakers[i]) if speakers and speakers[i] in own_refs else reference_lines(segments, i)
                for i in todo}
        prompts: dict[tuple, object] = {}
        samples: dict[tuple, object] = {}  # each reference's audio: the voice an accented line is converted into
        for i in todo:
            key = tuple(refs[i])
            if key and key not in prompts:
                first, last = segments[key[0]], segments[key[-1]]
                text = " ".join(segments[j].text.strip() for j in key)
                samples[key] = voice.cut(first.start, last.end)
                prompts[key] = engine.prompt(samples[key], text)
        if todo and not prompts:
            raise RuntimeError("No line of this video is short enough to copy the voice from")
        fallback = next(iter(prompts.values()), None)

        def prompt_for(i: int) -> object:
            return prompts.get(tuple(refs[i]), fallback)

        natural: list[float | None] = [None] * len(segments)
        for i in todo:
            natural[i] = engine.natural_seconds(segments[i].ru, prompt_for(i))
        rates = timing.plan_rates(segments, natural, min(max_speedup, MAX_RATE))

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
        report = check_report(clips_dir)
        best: dict[int, float] = {}
        asked: dict[int, float] = {}  # the seconds each kept try was asked for
        began = time.monotonic()
        total, done = len(missing), 0
        for attempt in range(1, (TRIES if listen else 1) + 1):
            if attempt == TRIES:  # the last try: at the voice's own pace
                missing = [(i, round(max(s, natural[i], min_seconds(segments[i].ru)), 2)) for i, s in missing]
            again = []
            n = 0
            while n < len(missing):
                group = missing[n:n + batch]
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
                for (i, seconds), audio in zip(group, audios, strict=True):
                    if listen is None:
                        write_wav(_level(audio), clips[i], SAMPLE_RATE)
                        continue
                    trial = clips[i].with_suffix(".try.wav")
                    write_wav(_level(audio), trial, SAMPLE_RATE)
                    heard = listen(trial, lang)
                    share = heard_share(segments[i].ru, heard)
                    if share > best.get(i, -1.0):
                        best[i], asked[i] = share, seconds
                        trial.replace(clips[i])
                        rates[i] = natural[i] / seconds
                        report[str(i)] = {"text": segments[i].ru, "heard": heard, "share": round(share, 2),
                                          "tries": attempt, "native": round(getattr(heard, "native", 1.0), 2)}
                    else:
                        trial.unlink()
                        report[str(i)]["tries"] = attempt
                    if share < HEARD_ENOUGH and attempt < TRIES:
                        again.append((i, seconds))
                n += len(group)
                if attempt == 1:
                    done += len(group)
                    print(f"Голос оригинала: {done}/{total} строк, {time.monotonic() - tick:.1f} с на группу, "
                          f"всего {time.monotonic() - began:.0f} с", flush=True)
                if progress:
                    progress(min(done / total, 1.0) * (0.85 if listen else 1.0) + (0.05 * (attempt - 1)))
            if listen:
                (clips_dir / CHECK_FILE).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
            if again:
                print(f"Голос оригинала: {len(again)} строк звучат неразборчиво — озвучиваю ещё раз "
                      f"(попытка {attempt + 1} из {TRIES})", flush=True)
            missing = again
        if listen and best:
            unclear = sum(share < HEARD_ENOUGH for share in best.values())
            print(f"Голос оригинала: проверено на слух {len(best)} строк, неразборчиво осталось {unclear}", flush=True)
            accented = [i for i in best if report[str(i)]["native"] < ACCENT_SURE and asked[i] >= ACCENT_MIN_SECONDS
                        and tuple(refs[i]) in samples]
            if accented:
                _fix_accents(accented, segments, lang, clips, clips_dir, asked, best, report, engine, listen,
                             native, converter, {i: tuple(refs[i]) for i in accented}, samples, batch)
                (clips_dir / CHECK_FILE).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        if progress and total:
            progress(1.0)
        return clips, rates
    finally:
        voice.close()
        if own:
            engine.close()
