"""Video sites besides YouTube (TikTok, Instagram, Facebook) and the login file ("cookies") the downloader uses.

Instagram, and many Facebook and some TikTok videos, are shown only to a logged-in user. The user saves their
browser's login for these sites as a cookies.txt file (Netscape format, e.g. with the "Get cookies.txt LOCALLY"
extension in Chrome or Edge) and adds it on the Settings page. Only cookies of the supported sites are kept; the file
stays on this computer (cookies.txt in the program folder, git-ignored) and is passed to yt-dlp (`download.base_opts`).
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


@dataclass(frozen=True)
class Site:
    key: str
    name: str
    domains: tuple[str, ...]  # cookie domains / link hosts (subdomains included)
    login_cookies: tuple[str, ...]  # present when the user is logged in


SITES = (
    Site("youtube", "YouTube", ("youtube.com", "youtu.be"), ("LOGIN_INFO", "__Secure-3PSID", "SAPISID")),
    Site("tiktok", "TikTok", ("tiktok.com",), ("sessionid", "sessionid_ss")),
    Site("instagram", "Instagram", ("instagram.com", "instagr.am"), ("sessionid",)),
    Site("facebook", "Facebook", ("facebook.com", "fb.watch", "fb.com"), ("c_user",)),
)

HEADER = "# Netscape HTTP Cookie File\n# Saved by Dubber: logins for YouTube, TikTok, Instagram, Facebook only.\n"
MAX_BYTES = 5_000_000


class CookieError(ValueError):
    """The uploaded file is not a cookies.txt file, or has no cookies of the supported sites."""


def _matches(host: str, domains: tuple[str, ...]) -> bool:
    host = host.lower().lstrip(".")
    return any(host == d or host.endswith("." + d) for d in domains)


def site_for_host(host: str) -> Site | None:
    return next((s for s in SITES if _matches(host, s.domains)), None)


def site_for_url(url: str) -> Site | None:
    return site_for_host(urlparse(url.strip()).hostname or "")


def video_id(extractor: str, raw_id: str) -> str:
    """A folder-safe id for work/<id>/: YouTube ids as they are (old caches keep working); other sites get their
    name in front (two sites can use the same number) and a hash when the id has other characters or is long."""
    extractor = re.sub(r"[^a-z0-9]", "", (extractor or "").lower())
    if extractor in ("", "youtube") and re.fullmatch(r"[A-Za-z0-9_-]{1,40}", raw_id):
        return raw_id
    prefix = extractor[:12] or "web"
    if re.fullmatch(r"[A-Za-z0-9_-]{1,40}", raw_id):
        return f"{prefix}-{raw_id}"
    return f"{prefix}-{hashlib.sha1(raw_id.encode()).hexdigest()[:16]}"


@dataclass(frozen=True)
class Cookie:
    domain: str
    line: str  # the line as written to the file
    name: str
    expires: int  # 0 = session cookie


def _from_json(text: str) -> str:
    """Cookie-Editor style JSON ([{domain, name, value, path, secure, expirationDate, httpOnly}, ...]) → Netscape."""
    import json

    try:
        items = json.loads(text)
    except ValueError:
        return ""
    lines = []
    for c in items if isinstance(items, list) else []:
        if not isinstance(c, dict) or not c.get("domain") or not c.get("name"):
            continue
        domain = str(c["domain"])
        prefix = "#HttpOnly_" if c.get("httpOnly") else ""
        sub = "TRUE" if domain.startswith(".") else "FALSE"
        secure = "TRUE" if c.get("secure") else "FALSE"
        expires = int(float(c.get("expirationDate") or 0))
        value = str(c.get("value", "")).replace("\t", " ").replace("\n", " ")
        lines.append(f"{prefix}{domain}\t{sub}\t{c.get('path') or '/'}\t{secure}\t{expires}\t{c['name']}\t{value}")
    return "\n".join(lines)


def parse(text: str) -> list[Cookie]:
    """Cookies of the supported sites from a Netscape cookies.txt text, or the JSON some extensions export (other
    sites' cookies are dropped)."""
    if text.lstrip().startswith("["):
        text = _from_json(text)
    cookies = []
    for raw in text.splitlines():
        line = raw.strip("\r\n")
        if line.startswith("#HttpOnly_"):  # curl / extensions mark HttpOnly cookies like this
            line = line[len("#HttpOnly_"):]
        elif not line.strip() or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) != 7:
            continue
        domain, _flag, _path, _secure, expires, name, _value = fields
        if not site_for_host(domain):
            continue
        try:
            stamp = int(float(expires or 0))
        except ValueError:
            continue
        cookies.append(Cookie(domain.lower(), raw.strip("\r\n"), name, stamp))
    return cookies


def merge(existing: str, uploaded: str) -> str:
    """The saved file after adding an upload: the upload replaces the saved cookies of every site it has (a new
    login), the other sites' saved cookies stay (files for different sites can be added one by one)."""
    new = parse(uploaded)
    if not new:
        raise CookieError("no cookies of the supported sites")
    renewed = {site_for_host(c.domain).key for c in new}
    kept = [c for c in parse(existing) if site_for_host(c.domain).key not in renewed]
    return HEADER + "".join(c.line + "\n" for c in kept + new)


def summary(text: str, now: float | None = None) -> list[dict]:
    """Per site: {site, name, logged_in, expires (unix time of the login cookie, 0 = until the browser closes)}."""
    now = time.time() if now is None else now
    out = []
    for site in SITES:
        login = [c for c in parse(text) if site_for_host(c.domain) == site and c.name in site.login_cookies
                 and (c.expires == 0 or c.expires > now)]
        out.append({"site": site.key, "name": site.name, "logged_in": bool(login),
                    "expires": max((c.expires for c in login), default=0)})
    return out


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
