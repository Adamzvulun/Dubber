"""Stage 4 — Russian text to speech, one audio clip per segment (Microsoft Edge neural voices)."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from collections.abc import Awaitable, Callable
from pathlib import Path

from .segments import Segment
from .timing import edge_rate

log = logging.getLogger(__name__)

VOICES = {
    "ru-RU-DmitryNeural": "Дмитрий (мужской голос)",
    "ru-RU-SvetlanaNeural": "Светлана (женский голос)",
}

# (text, voice, out_path, rate) -> None; rate is an Edge prosody rate such as "+0%" or "+35%"
SynthFn = Callable[[str, str, Path, str], Awaitable[None]]


async def edge_synthesize(text: str, voice: str, out_path: Path, rate: str = "+0%") -> None:
    import edge_tts

    # aiohttp ignores HTTPS_PROXY by itself; pass it explicitly so it works behind proxies.
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or None
    await edge_tts.Communicate(text, voice, rate=rate, proxy=proxy).save(str(out_path))


def clip_path(clips_dir: Path, index: int, text: str, rate: str = "+0%") -> Path:
    """Clip file for a line. The text is part of the name so a changed line never reuses a stale recording."""
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    suffix = "" if rate == "+0%" else f"_{rate.replace('%', '')}"
    return clips_dir / f"{index:05d}_{digest}{suffix}.mp3"


def speakable(text: str) -> bool:
    """Edge returns no audio for text without letters or digits ("…", "—", "♪"), so such lines get no clip."""
    return any(ch.isalnum() for ch in text)


def _no_audio(exc: Exception) -> bool:
    return type(exc).__name__ == "NoAudioReceived"  # edge_tts.exceptions.NoAudioReceived


async def _synthesize_all(
    segments: list[Segment],
    clips_dir: Path,
    voice: str,
    rates: list[str],
    synth: SynthFn,
    concurrency: int,
    retries: int,
    progress,
) -> list[Path | None]:
    clips_dir.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(concurrency)
    done = 0

    async def one(i: int, seg: Segment) -> Path | None:
        nonlocal done
        out = clip_path(clips_dir, i, seg.ru, rates[i])
        result: Path | None = out
        if not speakable(seg.ru):
            result = None
        elif not (out.exists() and out.stat().st_size > 0):
            async with semaphore:
                for attempt in range(retries + 1):
                    try:
                        await synth(seg.ru, voice, out, rates[i])
                        break
                    except Exception as exc:
                        out.unlink(missing_ok=True)
                        if attempt == retries:
                            if not _no_audio(exc):
                                raise
                            # Edge randomly answers "no audio" (~9% of requests, measured 2026-10-16). After all
                            # retries, one silent line is better than failing the whole video.
                            log.warning("No audio for line %d after %d attempts: %r", i, retries + 1, seg.ru)
                            result = None
                        else:
                            await asyncio.sleep(min(1.0 * (attempt + 1), 4.0))
        done += 1
        if progress:
            progress(done / len(segments))
        return result

    return list(await asyncio.gather(*(one(i, s) for i, s in enumerate(segments))))


def synthesize(
    segments: list[Segment],
    clips_dir: Path,
    voice: str = "ru-RU-DmitryNeural",
    synth: SynthFn | None = None,
    concurrency: int = 4,
    retries: int = 5,
    progress=None,
    rates: list[float] | None = None,
) -> list[Path | None]:
    """Speak every line into `clips_dir`; already-existing clips are reused (resume support).

    `rates` are speaking-rate factors per line (see `timing.plan_rates`); None = natural speed.
    Returns one path per segment, None where there is nothing to play (no speakable text, or Edge gave no audio).
    A line that fails at its planned rate falls back to its natural-speed clip when there is one.
    """
    if not segments:
        return []
    edge_rates = [edge_rate(r) for r in rates] if rates else ["+0%"] * len(segments)
    clips = asyncio.run(_synthesize_all(
        segments, clips_dir, voice, edge_rates, synth or edge_synthesize, concurrency, retries, progress
    ))
    for i, (seg, clip) in enumerate(zip(segments, clips, strict=True)):
        natural = clip_path(clips_dir, i, seg.ru)
        if clip is None and speakable(seg.ru) and natural.exists() and natural.stat().st_size > 0:
            clips[i] = natural
    wanted = [c for s, c in zip(segments, clips, strict=True) if speakable(s.ru)]
    if wanted and sum(c is None for c in wanted) > max(2, 0.2 * len(wanted)):
        # Many silent lines = the voice service is down or refusing us, not a random miss: say so.
        raise RuntimeError("Edge TTS: No audio was received for many lines")
    return clips
