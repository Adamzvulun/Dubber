"""Stage 4 — Russian text to speech, one audio clip per segment (Microsoft Edge neural voices)."""

from __future__ import annotations

import asyncio
import hashlib
import os
from collections.abc import Awaitable, Callable
from pathlib import Path

from .segments import Segment
from .timing import edge_rate

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


async def _synthesize_all(
    segments: list[Segment],
    clips_dir: Path,
    voice: str,
    rates: list[str],
    synth: SynthFn,
    concurrency: int,
    retries: int,
    progress,
) -> None:
    clips_dir.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(concurrency)
    done = 0

    async def one(i: int, seg: Segment) -> None:
        nonlocal done
        out = clip_path(clips_dir, i, seg.ru, rates[i])
        if seg.ru.strip() and not (out.exists() and out.stat().st_size > 0):
            async with semaphore:
                for attempt in range(retries + 1):
                    try:
                        await synth(seg.ru, voice, out, rates[i])
                        break
                    except Exception:
                        out.unlink(missing_ok=True)
                        if attempt == retries:
                            raise
                        await asyncio.sleep(1.5 * (attempt + 1))
        done += 1
        if progress:
            progress(done / len(segments))

    await asyncio.gather(*(one(i, s) for i, s in enumerate(segments)))


def synthesize(
    segments: list[Segment],
    clips_dir: Path,
    voice: str = "ru-RU-DmitryNeural",
    synth: SynthFn | None = None,
    concurrency: int = 4,
    retries: int = 2,
    progress=None,
    rates: list[float] | None = None,
) -> list[Path | None]:
    """Speak every line into `clips_dir`; already-existing clips are reused (resume support).

    `rates` are speaking-rate factors per line (see `timing.plan_rates`); None = natural speed.
    Returns one path per segment (None for segments with empty Russian text).
    """
    edge_rates = [edge_rate(r) for r in rates] if rates else ["+0%"] * len(segments)
    if segments:
        asyncio.run(_synthesize_all(
            segments, clips_dir, voice, edge_rates, synth or edge_synthesize, concurrency, retries, progress
        ))
    return [clip_path(clips_dir, i, s.ru, edge_rates[i]) if s.ru.strip() else None for i, s in enumerate(segments)]
