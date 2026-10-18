"""Hebrew pronunciation QA: how close does each voice come to the correct reading (incl. stress)?

    .venv/bin/python tools/qa_hebrew_voice.py OUT_DIR [N_SENTENCES] [CANDIDATES]

Sentences with gold IPA readings come from the heb-g2p-benchmark (built around homographs). Every candidate speaks
them, a Whisper fine-tuned to write Hebrew as IPA with stress (renikud/whisper-he-ipa) writes down what it heard, and
we count words that differ from the gold reading ("with stress") or differ in sounds ("sounds only"). The scorer
makes mistakes of its own, so only the comparison between candidates means something. Results: docs/RESEARCH.md.

Candidates: edge_avri, edge_hila (plain text, what Dubber does), edge_avri_niqqud (full niqqud from phonikud-onnx),
edge_avri_partial (niqqud only on words without vowel letters), piper_renikud (Phonikud's offline Piper voice).

Extra packages (not Dubber dependencies — use a throwaway venv or install into .venv):
    pip install phonikud-onnx renikud-onnx piper-onnx soundfile transformers torch
One-time scorer conversion (CTranslate2 int8, ~20x faster on CPU than transformers):
    ct2-transformers-converter --model renikud/whisper-he-ipa --output_dir OUT_DIR/whisper-he-ipa-ct2 \
        --quantization int8 --copy_files tokenizer.json preprocessor_config.json
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import numpy as np
import requests

GOLD_URL = "https://huggingface.co/spaces/Phonikud/heb-g2p-benchmark/raw/main/data/gt.tsv"
STRESS, METEG, PREFIX = "֫", "ֽ", "|"  # Phonikud's extra marks: stress, vocal shva, prefix boundary
HOLAM, QUBUTS, QAMATS_QATAN, DAGESH, VAV = "ֹ", "ֻ", "ׇ", "ּ", "ו"
MARKS = "[֑-ׇ]"
CANDIDATES = ["edge_avri", "edge_hila", "edge_avri_niqqud", "edge_avri_partial", "piper_renikud"]

_cache: dict = {}


def niqqud(text: str) -> str:
    if "nq" not in _cache:
        from huggingface_hub import hf_hub_download
        from phonikud_onnx import Phonikud

        _cache["nq"] = Phonikud(hf_hub_download("Phonikud/phonikud-onnx", "phonikud-1.0.int8.onnx"))
    return _cache["nq"].add_diacritics(text).replace(STRESS, "").replace(METEG, "").replace(PREFIX, "")


def for_edge(text: str) -> str:
    """Phonikud writes holam/qubuts on the letter before a plain vav (לִכְתֹּוב) and Edge then reads the vav as "v":
    move the vowel onto the vav (holam male / shuruk); qamats qatan becomes holam."""
    text = unicodedata.normalize("NFD", text)
    text = re.sub(f"{HOLAM}({MARKS}*){VAV}(?!{MARKS})", lambda m: m.group(1) + VAV + HOLAM, text)
    text = re.sub(f"{QUBUTS}({MARKS}*){VAV}(?!{MARKS})", lambda m: m.group(1) + VAV + DAGESH, text)
    text = re.sub(f"{QAMATS_QATAN}({MARKS}*){VAV}(?!{MARKS})", lambda m: m.group(1) + VAV + HOLAM, text)
    return unicodedata.normalize("NFC", text.replace(QAMATS_QATAN, HOLAM))


def has_vowel_letter(voc_word: str) -> bool:
    """A vav/yod without its own vowel (or וֹ / וּ) is a vowel letter: such a spelling already shows the vowel."""
    w = unicodedata.normalize("NFD", for_edge(voc_word))
    for i, ch in enumerate(w):
        if ch in "וי":
            marks = re.match(f"{MARKS}*", w[i + 1:]).group(0)
            if not marks or (ch == "ו" and marks in (HOLAM, DAGESH)):
                return True
    return False


def partial(text: str) -> str:
    out = []
    for plain, voc in zip(text.split(), niqqud(text).split(), strict=False):
        same = re.sub(MARKS, "", voc) == plain
        out.append(for_edge(voc) if same and not has_vowel_letter(voc) else plain)
    return " ".join(out)


def speak(candidate: str, text: str, path: Path) -> None:
    if path.exists():
        return
    if candidate.startswith("edge"):
        import edge_tts

        voice = "he-IL-HilaNeural" if candidate == "edge_hila" else "he-IL-AvriNeural"
        spoken = {"edge_avri_niqqud": lambda t: for_edge(niqqud(t)), "edge_avri_partial": partial}.get(
            candidate, lambda t: t)(text)
        proxy = os.environ.get("HTTPS_PROXY") or None
        asyncio.run(edge_tts.Communicate(spoken, voice, proxy=proxy).save(str(path)))
    elif candidate == "piper_renikud":
        import soundfile as sf
        from huggingface_hub import hf_hub_download
        from piper_onnx import Piper
        from renikud_onnx import G2P

        if "piper" not in _cache:
            repo = "Phonikud/phonikud-tts-checkpoints"
            _cache["piper"] = Piper(hf_hub_download(repo, "model.onnx"), hf_hub_download(repo, "model.config.json"))
            _cache["g2p"] = G2P()
        samples, rate = _cache["piper"].create(_cache["g2p"].phonemize(text), is_phonemes=True)
        sf.write(str(path), np.clip(samples * 2, -1, 1), rate)
    else:
        raise ValueError(candidate)


def hear(path: Path, scorer: Path) -> str:
    if "asr" not in _cache:
        from faster_whisper import WhisperModel

        _cache["asr"] = WhisperModel(str(scorer), device="cpu", compute_type="int8")
    raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", str(path), "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    segments, _ = _cache["asr"].transcribe(np.frombuffer(raw, np.float32), language="he", beam_size=5,
                                           vad_filter=False, condition_on_previous_text=False)
    return " ".join(s.text for s in segments).strip()


def words(ipa: str) -> list[str]:
    """IPA words in the scorer's ASCII-like notation (it writes ' for stress, r for ʁ, x for χ, S for ʃ, q for ʔ)."""
    ipa = unicodedata.normalize("NFC", ipa)
    for a, b in {"ɡ": "g", "ˈ": "'", "ʁ": "r", "χ": "x", "ʃ": "S", "ʔ": "q", "ʒ": "Z"}.items():
        ipa = ipa.replace(a, b)
    return re.sub(r"[^\w\s']", " ", ipa).split()


def edit_distance(a: list[str], b: list[str]) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def main() -> None:
    out = Path(sys.argv[1])
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    candidates = sys.argv[3].split(",") if len(sys.argv) > 3 else CANDIDATES
    out.mkdir(parents=True, exist_ok=True)
    gold_file = out / "gt.tsv"
    if not gold_file.exists():
        gold_file.write_bytes(requests.get(GOLD_URL, timeout=60).content)
    gold = [line.split("\t") for line in gold_file.read_text(encoding="utf-8").splitlines()][:n]
    scorer = out / "whisper-he-ipa-ct2"
    totals = {c: [0, 0, 0] for c in candidates}
    rows = []
    for i, (text, reading) in enumerate(gold):
        ref = words(reading)
        for c in candidates:
            path = out / f"{i:03d}_{c}.{'wav' if c.startswith('piper') else 'mp3'}"
            speak(c, text, path)
            heard = hear(path, scorer)
            hyp = words(heard)
            full = edit_distance(ref, hyp)
            sounds = edit_distance([w.replace("'", "") for w in ref], [w.replace("'", "") for w in hyp])
            totals[c][0] += full
            totals[c][1] += sounds
            totals[c][2] += len(ref)
            rows.append({"n": i, "candidate": c, "text": text, "gold": reading, "heard": heard, "errors": full})
        print(i, " ".join(f"{r['candidate']}={r['errors']}" for r in rows[-len(candidates):]), flush=True)
    (out / "rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nWord errors vs the gold reading, {len(gold)} sentences (lower is better):")
    for c, (full, sounds, total) in totals.items():
        print(f"  {c:18s} with stress {full / total:.3f}   sounds only {sounds / total:.3f}")


if __name__ == "__main__":
    main()
