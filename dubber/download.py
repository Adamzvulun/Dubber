"""Stage 1 — get the source video (YouTube URL via yt-dlp, or a local file)."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class VideoInfo:
    id: str
    title: str
    path: Path


def is_url(source: str) -> bool:
    """A web address worth trying: http(s), a host with a dot (or localhost) and no spaces."""
    from urllib.parse import urlparse

    source = source.strip()
    if not re.match(r"^https?://", source, re.IGNORECASE) or re.search(r"\s", source):
        return False
    host = urlparse(source).hostname or ""
    return host == "localhost" or bool(re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", host, re.IGNORECASE))


def local_video_id(path: Path) -> str:
    stat = path.stat()
    digest = hashlib.sha1(f"{path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}".encode()).hexdigest()
    return f"local-{digest[:12]}"


def find_deno() -> str | None:
    """The deno JavaScript runtime YouTube extraction needs. Installed into the venv by pip (`deno` package)."""
    bin_dir = Path(sys.executable).parent
    for name in ("deno", "deno.exe"):
        if (bin_dir / name).is_file():
            return str(bin_dir / name)
    return shutil.which("deno")


def base_opts() -> dict:
    opts = {"quiet": True, "no_warnings": True, "noprogress": True, "noplaylist": True}
    # Optional browser cookies (Netscape cookies.txt) for when YouTube asks to "confirm you're not a bot".
    cookies = os.environ.get("DUBBER_COOKIES")
    if cookies:
        if not Path(cookies).expanduser().is_file():
            raise FileNotFoundError(f"DUBBER_COOKIES points to a missing file: {cookies}")
        opts["cookiefile"] = str(Path(cookies).expanduser())
    deno = find_deno()
    if deno:
        opts["js_runtimes"] = {"deno": {"path": deno}}
    return opts


def fetch_info(url: str) -> dict:
    """Video metadata without downloading (id, title, duration...)."""
    import yt_dlp

    with yt_dlp.YoutubeDL(base_opts()) as ydl:
        return ydl.extract_info(url, download=False)


def download(source: str, dest_dir: Path, max_height: int = 720, progress=None) -> VideoInfo:
    """Download (or copy) the source video into `dest_dir/source.mp4`.

    `progress(fraction)` is called with 0..1 while downloading, if given.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / "source.mp4"

    if not is_url(source):
        path = Path(source).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Not a URL and not an existing file: {source}")
        if not target.exists():
            shutil.copyfile(path, target)
        return VideoInfo(id=local_video_id(path), title=path.stem, path=target)

    import yt_dlp

    def hook(d: dict) -> None:
        if progress and d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if total:
                progress(min(1.0, d.get("downloaded_bytes", 0) / total))

    opts = {
        **base_opts(),
        # Prefer H.264 + AAC: plays everywhere (Windows player, browsers, phones).
        "format": (
            f"bv*[vcodec^=avc1][height<={max_height}]+ba[ext=m4a]/"
            f"bv*[height<={max_height}]+ba/b[height<={max_height}]/bv*+ba/b"
        ),
        "merge_output_format": "mp4",
        "outtmpl": str(dest_dir / "source.%(ext)s"),
        "progress_hooks": [hook],
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(source, download=not target.exists())
    if not target.exists():
        # yt-dlp may pick another container if merging was impossible
        candidates = sorted(dest_dir.glob("source.*"))
        if not candidates:
            raise RuntimeError("yt-dlp finished but no video file was written")
        candidates[0].rename(target)
    return VideoInfo(id=info["id"], title=info.get("title") or info["id"], path=target)
