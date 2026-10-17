"""Dub multilingual test clips into every dub language with the REAL pipeline and measure each result.

    .venv/bin/python tools/qa_languages.py OUT_DIR [--clips mixed,trio] [--targets ru,he,...] [--translator offline]

For each (clip, target): untranslated lines (quality-gate rule), Whisper re-listening the dubbed track in the target
language (similarity to the intended text), timing.json (late lines, rate range) and an NLLB back-translation of every
line into English, so a human can judge the meaning. Results: OUT_DIR/results.json + OUT_DIR/table.md. Resumable:
pairs already in results.json are skipped. Needs network for Edge TTS (and Hugging Face on first use).

Clips (synthetic speech, made once with Edge voices into OUT_DIR/clips/):
  mixed — English + French (33 s), trio — English + Spanish + German (29 s).
Use --translator auto to test the Google path (from a home connection; cloud IPs get HTTP 429).
Session 2026-10-17 results: docs/RESEARCH.md "Every dub language".
"""

from __future__ import annotations

import argparse
import asyncio
import difflib
import json
import os
import re
import subprocess
import time
import unicodedata
from pathlib import Path

from dubber import languages, pipeline
from dubber.config import Settings
from dubber.media import decode_audio
from dubber.translate import NllbBackend, needs_retry

CLIPS = {
    "mixed": [
        ("en-US-AndrewNeural", "Welcome back. Today we visit a small bakery in Paris and talk to the owner about her "
                               "work. Let's hear what she says."),
        ("fr-FR-DeniseNeural", "Bonjour à tous. Je fais du pain ici depuis vingt ans. Chaque matin, je commence "
                               "à quatre heures. Le secret, c'est la patience et une bonne farine. Mes clients "
                               "viennent tous les jours, et je connais presque tout le monde dans le quartier."),
        ("en-US-AndrewNeural", "So patience and good flour are the secret. That's a lesson for any craft, not only "
                               "baking. Thanks for watching."),
    ],
    "trio": [
        ("en-US-AvaNeural", "Hi everyone. Today I asked two friends how they start their working day."),
        ("es-ES-AlvaroNeural", "Yo empiezo con un café y una lista corta de tareas. Nunca miro el correo antes de las "
                               "diez, porque me roba la concentración."),
        ("de-DE-KatjaNeural", "Ich gehe morgens zuerst spazieren. Danach plane ich die drei wichtigsten Aufgaben und "
                              "schalte mein Telefon aus."),
        ("en-US-AvaNeural", "Two different habits, one idea: protect your attention in the morning."),
    ],
}


def make_clip(name: str, folder: Path) -> Path:
    """Speak the clip's parts with Edge voices (1 s pause between speakers) into a black-screen MP4."""
    import edge_tts

    out = folder / f"{name}.mp4"
    if out.exists():
        return out
    folder.mkdir(parents=True, exist_ok=True)
    proxy = os.environ.get("HTTPS_PROXY") or None
    parts = [folder / f"{name}_{i}.mp3" for i in range(len(CLIPS[name]))]

    async def speak() -> None:
        for (voice, text), path in zip(CLIPS[name], parts, strict=True):
            await edge_tts.Communicate(text, voice, proxy=proxy).save(str(path))

    asyncio.run(speak())
    inputs = [arg for p in parts for arg in ("-i", str(p))]
    pads = "".join(f"[{i}:a]apad=pad_dur=1[a{i}];" for i in range(len(parts) - 1))
    chain = "".join(f"[a{i}]" for i in range(len(parts) - 1)) + f"[{len(parts) - 1}:a]"
    audio = folder / f"{name}.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex",
                    f"{pads}{chain}concat=n={len(parts)}:v=0:a=1[o]", "-map", "[o]", str(audio)], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x240:r=5", "-i",
                    str(audio), "-shortest", "-c:v", "libx264", "-c:a", "aac", str(out)], check=True)
    return out


def _norm(text: str) -> str:
    return re.sub(r"[\W_]+", "", unicodedata.normalize("NFKC", text).lower())


def relisten(whisper, work: Path, folder: Path, target: str) -> tuple[float, str]:
    """Whisper (forced to the dub language) listens to the voice-only dub track; similarity to the intended text."""
    meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    segments = json.loads((folder / "segments.json").read_text(encoding="utf-8"))
    track = max((work / meta["id"]).glob(f"dub_track_{meta['voice']}_*.wav"), key=lambda p: p.stat().st_mtime)
    heard_segments, _ = whisper.transcribe(decode_audio(track, 16000), language=target, beam_size=5, vad_filter=True)
    heard = " ".join(s.text.strip() for s in heard_segments)
    said = " ".join(s["ru"] for s in segments)
    # autojunk=False: the default treats frequent characters of long texts as junk and ruins the score.
    return round(difflib.SequenceMatcher(None, _norm(said), _norm(heard), autojunk=False).ratio(), 3), heard


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out", type=Path)
    ap.add_argument("--clips", default="mixed,trio")
    ap.add_argument("--targets", default=",".join(languages.LANGUAGES))
    ap.add_argument("--translator", default="offline", help="offline (default), auto, google or claude")
    args = ap.parse_args()

    from faster_whisper import WhisperModel

    whisper = WhisperModel("small", device="auto", compute_type="int8")
    out: Path = args.out
    work = out / "work"
    res_file = out / "results.json"
    results = json.loads(res_file.read_text(encoding="utf-8")) if res_file.exists() else []
    done = {(r["clip"], r["target"]) for r in results}

    for clip in args.clips.split(","):
        video = make_clip(clip, out / "clips")
        for target in args.targets.split(","):
            if (clip, target) in done:
                continue
            lang = languages.get(target)
            settings = Settings(work_dir=work, output_dir=out / f"out_{clip}_{target}", target_lang=target,
                                voice="male", translator=args.translator)
            started = time.time()
            try:
                result = pipeline.run(str(video), settings, progress=lambda label, fraction: None)
            except Exception as exc:  # recorded, the run goes on
                print(json.dumps({"clip": clip, "target": target, "FAILED": f"{type(exc).__name__}: {exc}"},
                                 ensure_ascii=False), flush=True)
                continue
            segments = json.loads((result.folder / "segments.json").read_text(encoding="utf-8"))
            timing = json.loads((result.folder / "timing.json").read_text(encoding="utf-8"))
            meta = json.loads((result.folder / "meta.json").read_text(encoding="utf-8"))
            similarity, heard = relisten(whisper, work, result.folder, target)
            dubbed = [s["ru"] for s in segments]
            back = NllbBackend("en").translate_group(dubbed, target) if target != "en" else dubbed
            row = {
                "clip": clip, "target": target, "lines": len(segments),
                "langs": sorted({s.get("lang", "") for s in segments}),
                "untranslated": [s["text"] for s in segments
                                 if needs_retry(s["text"], s["ru"], s.get("lang", ""), lang)],
                "relisten_similarity": similarity, "heard": heard,
                "late_lines": timing["late_lines"], "max_delay": timing["max_delay"],
                "rates": [min((d["rate"] for d in timing["detail"]), default=1.0), timing["median_rate"],
                          timing["max_rate"]],
                "translator": meta.get("translator"), "seconds": round(time.time() - started),
                "pairs": [{"lang": s.get("lang"), "src": s["text"], "dub": s["ru"], "back": b}
                          for s, b in zip(segments, back, strict=True)],
            }
            results.append(row)
            print(json.dumps({k: v for k, v in row.items() if k not in ("pairs", "heard")}, ensure_ascii=False),
                  flush=True)
            res_file.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")

    rows = ["| Clip | Dub | Untranslated | Re-heard | Late lines | Rates | Translator |",
            "|---|---|---|---|---|---|---|"]
    rows += [f"| {r['clip']} | {r['target']} | {len(r['untranslated'])} | {r['relisten_similarity'] * 100:.0f}% | "
             f"{r['late_lines']} | {r['rates'][0]:.2f}–{r['rates'][2]:.2f}× | {r['translator']} |" for r in results]
    (out / "table.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print("DONE — see", out / "table.md", flush=True)


if __name__ == "__main__":
    main()
