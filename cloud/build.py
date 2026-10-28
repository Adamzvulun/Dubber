"""Build the phone app for the mailbox worker: the website's own files (dubber/web/) → cloud/worker/public/.

    python cloud/build.py        # then: cd cloud/worker && npx wrangler deploy   (the deploy workflow does both)

Same files as on the PC; app.js switches to phone mode by itself when it runs under /p/<token>/ (ADR-033).
Only index.html changes: its file addresses get the version tag, like dubber/app.py does on the PC.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "dubber" / "web"
PUBLIC = ROOT / "cloud" / "worker" / "public"


def version() -> str:
    text = (ROOT / "dubber" / "__init__.py").read_text(encoding="utf-8")
    return re.search(r'__version__\s*=\s*"([^"]+)"', text).group(1)


def build(web: Path = WEB, public: Path = PUBLIC) -> Path:
    digest = hashlib.sha256()
    for f in sorted(p for p in web.rglob("*") if p.is_file()):
        digest.update(f.relative_to(web).as_posix().encode() + f.read_bytes())
    tag = f"{version()}.{digest.hexdigest()[:8]}"
    if public.exists():
        shutil.rmtree(public)
    shutil.copytree(web, public)
    index = public / "index.html"
    index.write_text(index.read_text(encoding="utf-8").replace("__ASSETS__", tag), encoding="utf-8")
    return public


if __name__ == "__main__":
    out = build(*(Path(a) for a in sys.argv[1:3]))
    print(f"phone app built: {out}")
