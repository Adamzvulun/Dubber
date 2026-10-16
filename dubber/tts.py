"""Stage 4 — Russian text to speech, one audio clip per segment (Microsoft Edge neural voices)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path

from .segments import Segment

VOICES = {
    "ru-RU-DmitryNeural": "Дмитрий (мужской голос)",
    "ru-RU-SvetlanaNeural": "Светлана (женский голос)",
}

# (text, voice, out_path) -> None
SynthFn = Callable[[str, str, Path], Awaitable[None]]


async def edge_synthesize(text: str, voice: str, out_path: Path) -> None:
    import edge_tts

    await edge_tts.Communicate(text, voice).save(str(out_path))


def clip_path(clips_dir: Path, index: int) -> Path:
    return clips_dir / f"{index:05d}.mp3"


async def _synthesize_all(
    segments: list[Segment],
    clips_dir: Path,
    voice: str,
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
        out = clip_path(clips_dir, i)
        if seg.ru.strip() and not (out.exists() and out.stat().st_size > 0):
            async with semaphore:
                for attempt in range(retries + 1):
                    try:
                        await synth(seg.ru, voice, out)
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
) -> list[Path | None]:
    """Create `clips_dir/00000.mp3`, ... Already-existing clips are reused (resume support).

    Returns one path per segment (None for segments with empty Russian text).
    """
    if segments:
        asyncio.run(
            _synthesize_all(segments, clips_dir, voice, synth or edge_synthesize, concurrency, retries, progress)
        )
    return [clip_path(clips_dir, i) if s.ru.strip() else None for i, s in enumerate(segments)]
