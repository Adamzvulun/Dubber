"""Who says each line: a voice print per line, lines with matching prints = one speaker (ADR-038).

Used by the original voice («Оригинал», clone.py): each speaker's voice is copied from one longer sample of them, and
the dub lines of different speakers may overlap as they did in the original (align.py).

The voice print is 3D-Speaker's CAM++ model (Apache-2.0, 28 MB, run by sherpa-onnx on the processor). Measured on a
3-voice test conversation (English + French, docs/RESEARCH.md): lines of the same speaker matched at >= 0.71, of
different speakers at <= 0.19. A full diarization (pyannote segmentation + clustering) merged two male voices that took
turns quickly, so the lines Whisper already cut are grouped instead.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from .hub import retry

MODEL_REPO = "csukuangfj/speaker-embedding-models"
MODEL_FILE = "3dspeaker_speech_campplus_sv_zh_en_16k-common_advanced.onnx"
SAMPLE_RATE = 16000
SAME_SPEAKER = 0.45  # voice prints this similar (cosine) are one speaker: measured >= 0.71 same, <= 0.19 different
MIN_PRINT = 0.5  # seconds: shorter lines get no voice print (they go with the nearest line in time)
RELIABLE = 1.0  # seconds: shorter lines only join a speaker, they never start one

# (16-kHz samples of the whole voice track, start, end) -> the line's voice print (a unit vector)
Extractor = Callable[["object", float, float], "object"]


def group(prints: Sequence, durations: Sequence[float]) -> list[int | None]:
    """Speaker number per line (0, 1, … in order of first appearance; None = unknown).

    Lines of at least RELIABLE seconds are grouped (average linkage: two groups join while their lines are on average
    at least SAME_SPEAKER alike); shorter lines join the group they are most like."""
    import numpy as np

    sure = [i for i, (p, d) in enumerate(zip(prints, durations, strict=True)) if p is not None and d >= RELIABLE]
    groups: list[list[int]] = [[i] for i in sure]
    if sure:
        vectors = np.stack([prints[i] for i in sure])
        sim = vectors @ vectors.T
        index = {line: k for k, line in enumerate(sure)}

        def alike(a: list[int], b: list[int]) -> float:
            return float(sim[np.ix_([index[i] for i in a], [index[j] for j in b])].mean())

        while len(groups) > 1:
            score, x, y = max((alike(groups[x], groups[y]), x, y)
                              for x in range(len(groups)) for y in range(x + 1, len(groups)))
            if score < SAME_SPEAKER:
                break
            groups[x] += groups.pop(y)

    of: dict[int, int] = {line: g for g, members in enumerate(groups) for line in members}
    if groups:
        centres = [np.mean([prints[i] for i in members], axis=0) for members in groups]
        for i, p in enumerate(prints):
            if p is not None and i not in of:
                of[i] = int(np.argmax([float(p @ c) for c in centres]))
    # numbered in the order the speakers first speak
    order: dict[int, int] = {}
    for i in sorted(of):
        order.setdefault(of[i], len(order))
    return [order[of[i]] if i in of else None for i in range(len(prints))]


def assign(segments: Sequence, samples, extractor: Extractor | None = None) -> list[int | None]:
    """Speaker number per line, from the 16-kHz voice track `samples` (the voice separate.py split off)."""
    extractor = extractor or VoicePrints()
    prints = [extractor(samples, s.start, s.end) if s.end - s.start >= MIN_PRINT else None for s in segments]
    who = group(prints, [s.end - s.start for s in segments])
    known = [i for i, w in enumerate(who) if w is not None]
    def gap(i: int, j: int) -> float:
        return max(segments[j].start - segments[i].end, segments[i].start - segments[j].end)

    for i, w in enumerate(who):
        if w is None and known:  # e.g. "Да.": with the nearest line in time
            who[i] = who[min(known, key=lambda j: gap(i, j))]  # noqa: B023 (used at once)
    return who


class VoicePrints:
    """The CAM++ voice-print model (downloaded once from Hugging Face)."""

    def __init__(self):
        import sherpa_onnx
        from huggingface_hub import hf_hub_download

        path = retry(lambda: hf_hub_download(MODEL_REPO, MODEL_FILE))
        self.model = sherpa_onnx.SpeakerEmbeddingExtractor(
            sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=path, num_threads=2))

    def __call__(self, samples, start: float, end: float):
        import numpy as np

        stream = self.model.create_stream()
        stream.accept_waveform(SAMPLE_RATE, samples[int(start * SAMPLE_RATE):int(end * SAMPLE_RATE)])
        stream.input_finished()
        vector = np.array(self.model.compute(stream), dtype=np.float32)
        return vector / (np.linalg.norm(vector) or 1.0)
