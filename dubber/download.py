"""Stage 1 — get the source video (a YouTube, TikTok, Instagram or Facebook link via yt-dlp, or a local file)."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from . import media, sites


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


def cookie_file() -> Path:
    """The login file (Netscape cookies.txt): DUBBER_COOKIES, else cookies.txt in the program folder, which the
    Settings page writes (`dubber/sites.py`). Used for login-only videos (Instagram, Facebook, TikTok) and when
    YouTube asks to "confirm you're not a bot"."""
    from .config import PROJECT_ROOT

    return Path(os.environ.get("DUBBER_COOKIES") or PROJECT_ROOT / "cookies.txt").expanduser()


def base_opts(cookies: Path | None = None) -> dict:
    opts = {"quiet": True, "no_warnings": True, "noprogress": True, "noplaylist": True}
    explicit = os.environ.get("DUBBER_COOKIES")
    cookies = cookies or cookie_file()
    if explicit and not cookies.is_file():
        raise FileNotFoundError(f"DUBBER_COOKIES points to a missing file: {explicit}")
    if cookies.is_file():
        opts["cookiefile"] = str(cookies)
    deno = find_deno()
    if deno:
        opts["js_runtimes"] = {"deno": {"path": deno}}
    return opts


def playlist_entries(url: str, limit: int = 200) -> dict:
    """{title, entries: [{url, title}]} of a playlist (or the playlist a video link carries), without downloading."""
    import yt_dlp

    opts = {**base_opts(), "noplaylist": False, "extract_flat": "in_playlist", "playlistend": limit}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    entries = []
    for entry in info.get("entries") or []:
        vid = entry.get("id")
        if not vid:  # private or deleted videos have no id
            continue
        link = entry.get("url") or ""
        if not link.startswith("http"):
            link = f"https://www.youtube.com/watch?v={vid}"  # only YouTube lists come here (the page asks)
        entries.append({"url": link, "title": entry.get("title") or vid})
    return {"title": info.get("title") or "", "entries": entries[:limit]}


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
            _save_playable(path, target, max_height, copy=True)
        return VideoInfo(id=local_video_id(path), title=path.stem, path=target)

    import yt_dlp

    def hook(d: dict) -> None:
        if progress and d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if total:
                progress(min(1.0, d.get("downloaded_bytes", 0) / total))

    opts = {
        **base_opts(),
        # Prefer H.264 + AAC: plays everywhere (Windows player, browsers, phones). TikTok, Instagram and Facebook
        # mostly offer video and sound together in one file ("b"), TikTok often in HEVC: H.264 first there too.
        "format": (
            f"bv*[vcodec^=avc1][height<={max_height}]+ba[ext=m4a]/"
            f"b[vcodec^=avc1][height<={max_height}]/"
            f"bv*[height<={max_height}]+ba/b[height<={max_height}]/bv*+ba/b"
        ),
        "merge_output_format": "mp4",
        "outtmpl": str(dest_dir / "download.%(ext)s"),
        "progress_hooks": [hook],
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(source, download=not target.exists())
    if not target.exists():
        # yt-dlp may pick another container if merging was impossible
        candidates = sorted(p for p in dest_dir.glob("download.*") if not p.name.endswith(".part"))
        if not candidates:
            raise RuntimeError("yt-dlp finished but no video file was written")
        _save_playable(candidates[0], target, max_height)
    vid = sites.video_id(info.get("extractor_key") or info.get("extractor") or "", str(info["id"]))
    return VideoInfo(id=vid, title=info.get("title") or str(info["id"]), path=target)


def _save_playable(src: Path, target: Path, max_height: int, copy: bool = False) -> None:
    """Put the video at `target` as H.264 (re-encoded only when it is something else, e.g. HEVC from TikTok or an
    iPhone, which many Windows browsers can't play; the dub keeps the video as it is)."""
    partial = target.with_name("source.partial.mp4")
    if media.video_codec(src) not in ("h264", ""):
        media.to_h264(src, partial, max_height)
        partial.replace(target)
        if not copy:
            src.unlink(missing_ok=True)
    elif copy:
        shutil.copyfile(src, partial)
        partial.replace(target)
    else:
        src.replace(target)
