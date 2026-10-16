"""Downloading the free AI models (Whisper, the offline translator) from Hugging Face on first use."""

from __future__ import annotations

import time


def retry(fn, attempts: int = 3, wait: float = 5.0, sleep=time.sleep):
    """Call `fn()`; on an error try again (waiting longer each time), re-raising the last error.

    Model downloads are large (Whisper "small" is ~500 MB) and a home connection may drop mid-way;
    files already fetched stay in the cache, so a retry resumes rather than starting over.
    """
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception:
            if attempt == attempts:
                raise
            sleep(wait * attempt)
