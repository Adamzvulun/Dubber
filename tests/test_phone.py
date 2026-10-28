import io
import json
import tarfile
import threading
import urllib.error

import pytest

from dubber import phone


@pytest.fixture(autouse=True)
def no_real_settings(monkeypatch):
    monkeypatch.delenv(phone.TOKEN_KEY, raising=False)
    monkeypatch.setenv("DUBBER_MAILBOX_URL", "https://dubber.example.workers.dev")


def test_household_token_is_made_once_and_kept(tmp_path):
    env = tmp_path / ".env"
    env.write_text("ANTHROPIC_API_KEY=x\n", encoding="utf-8")
    token = phone.household_token(env)
    assert len(token) >= 43 and f"{phone.TOKEN_KEY}={token}" in env.read_text(encoding="utf-8")
    assert "ANTHROPIC_API_KEY=x" in env.read_text(encoding="utf-8")
    assert phone.household_token(env) == token
    assert phone.pair_url(token) == f"https://dubber.example.workers.dev/p/{token}/"


@pytest.mark.parametrize(("system", "machine", "asset"), [
    ("win32", "AMD64", "cloudflared-windows-amd64.exe"),
    ("win32", "x86", "cloudflared-windows-386.exe"),
    ("linux", "x86_64", "cloudflared-linux-amd64"),
    ("linux", "aarch64", "cloudflared-linux-arm64"),
    ("darwin", "arm64", "cloudflared-darwin-arm64.tgz"),
    ("darwin", "x86_64", "cloudflared-darwin-amd64.tgz"),
    ("sunos5", "x86_64", None),
])
def test_cloudflared_asset_per_computer(system, machine, asset):
    assert phone.cloudflared_asset(system, machine) == asset


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def test_download_plain_and_tgz(tmp_path):
    asked = []

    def opener(url, timeout):
        asked.append(url)
        return FakeResponse(b"BINARY")

    exe = phone.download_cloudflared(tmp_path / "a", opener, asset="cloudflared-linux-amd64")
    assert exe.read_bytes() == b"BINARY" and exe.stat().st_mode & 0o111
    assert asked == [phone.RELEASES + "cloudflared-linux-amd64"]
    assert not list((tmp_path / "a").glob("*.part"))

    packed = io.BytesIO()
    with tarfile.open(fileobj=packed, mode="w:gz") as archive:
        info = tarfile.TarInfo("cloudflared")
        info.size = 3
        archive.addfile(info, io.BytesIO(b"MAC"))
    exe = phone.download_cloudflared(tmp_path / "b", lambda url, timeout: FakeResponse(packed.getvalue()),
                                     asset="cloudflared-darwin-arm64.tgz")
    assert exe.read_bytes() == b"MAC" and not list((tmp_path / "b").glob("*.tgz*"))


class FakeProc:
    def __init__(self, lines):
        self.stderr = iter(lines)
        self.terminated = False

    def wait(self):
        return 0

    def poll(self):
        return 0

    def terminate(self):
        self.terminated = True


def test_tunnel_reports_its_address_and_restarts():
    runs = [
        ["INF Requesting new quick Tunnel on trycloudflare.com...\n",
         "ERR failed to reach https://api.trycloudflare.com/tunnel\n",
         "INF |  https://brave-lucky-words-here.trycloudflare.com  |\n"],
        ["INF |  https://second-run-address.trycloudflare.com  |\n"],
    ]
    seen, commands = [], []
    tunnel = None

    def popen(cmd, **kw):
        commands.append(cmd)
        if not runs:
            raise OSError("gone")
        return FakeProc(runs.pop(0))

    def sleep(seconds):
        if not runs:
            tunnel.stop()

    tunnel = phone.Tunnel(phone.Path("/x/cloudflared"), 7860, seen.append, popen=popen, sleep=sleep)
    tunnel.run()
    assert commands[0] == ["/x/cloudflared", "tunnel", "--no-autoupdate", "--url", "http://127.0.0.1:7860"]
    assert seen == ["https://brave-lucky-words-here.trycloudflare.com", None,
                    "https://second-run-address.trycloudflare.com", None]


class FakeMailbox:
    def __init__(self, links=(), fail=False):
        self.box = list(links)
        self.announced, self.deleted, self.fail = [], [], fail

    def announce(self, url):
        if self.fail:
            raise urllib.error.URLError("offline")
        self.announced.append(url)

    def links(self):
        if self.fail:
            raise urllib.error.URLError("offline")
        return list(self.box)

    def delete(self, link_id):
        self.deleted.append(link_id)
        self.box = [link for link in self.box if link["id"] != link_id]


def bridge(tmp_path, mailbox, submitted, clock=lambda: 1000.0):
    return phone.PhoneBridge(tmp_path / ".env", 7860, submitted.append, tools=tmp_path / "cf", mailbox=mailbox,
                             clock=clock)


def test_bridge_announces_address_and_starts_queued_links(tmp_path):
    links = [{"id": "1", "url": "https://youtu.be/a", "lang": "he"}, {"id": "2", "url": "https://youtu.be/b"}]
    box, submitted = FakeMailbox(links), []
    now = [1000.0]
    b = bridge(tmp_path, box, submitted, clock=lambda: now[0])
    b.tick()  # no tunnel yet: links are still taken in (the PC is on)
    assert [s["id"] for s in submitted] == ["1", "2"] and box.deleted == ["1", "2"] and box.announced == []

    b._on_url("https://a-b.trycloudflare.com")
    assert b.public()["status"] == "ready" and b.public()["connected"]
    b.tick()
    b.tick()  # not again within ANNOUNCE_EVERY
    assert box.announced == ["https://a-b.trycloudflare.com"]
    now[0] += phone.ANNOUNCE_EVERY + 1
    b.tick()
    assert len(box.announced) == 2
    assert b.public()["pair_url"].endswith(f"/p/{b.token}/")


def test_bridge_survives_an_unreachable_mailbox(tmp_path, capsys):
    b = bridge(tmp_path, FakeMailbox(fail=True), [])
    b._on_url("https://a-b.trycloudflare.com")
    b.tick()
    assert "недоступен" in capsys.readouterr().out


def test_bridge_without_a_mailbox_is_unconfigured(tmp_path, monkeypatch):
    monkeypatch.setenv("DUBBER_MAILBOX_URL", "")
    monkeypatch.setattr(phone, "MAILBOX_URL", "")
    b = phone.PhoneBridge(tmp_path / ".env", 7860, lambda link: None, tools=tmp_path / "cf").start()
    assert b.public() == {"status": "unconfigured", "pair_url": None, "connected": False}


def test_bridge_downloads_cloudflared_then_starts_the_tunnel(tmp_path):
    started = threading.Event()

    class Tunnel:
        def __init__(self, exe, port, on_url):
            self.exe, self.on_url = exe, on_url

        def run(self):
            self.on_url("https://x-y.trycloudflare.com")
            started.set()

        def stop(self):
            pass

    def download(tools):
        tools.mkdir(parents=True)
        exe = phone.cloudflared_path(tools)
        exe.write_bytes(b"x")
        return exe

    box = FakeMailbox()
    b = phone.PhoneBridge(tmp_path / ".env", 7860, lambda link: None, tools=tmp_path / "cf", mailbox=box,
                          tunnel_factory=Tunnel, download=download).start()
    assert started.wait(5)
    for _ in range(100):
        if box.announced:
            break
        threading.Event().wait(0.02)
    b.stop()
    assert b.tunnel.exe == phone.cloudflared_path(tmp_path / "cf")
    assert box.announced == ["https://x-y.trycloudflare.com"]


def test_mailbox_client_sends_the_token(tmp_path):
    sent = []

    def opener(request, timeout):
        sent.append((request.method, request.full_url, request.headers.get("X-dubber-token"),
                     request.data and json.loads(request.data)))
        return FakeResponse(json.dumps({"pc": None, "links": [{"id": "9"}]}).encode())

    box = phone.Mailbox("https://m.example/", "t" * 43, opener)
    box.announce("https://a-b.trycloudflare.com")
    assert box.links() == [{"id": "9"}]
    box.delete("9")
    assert [s[:2] for s in sent] == [("PUT", "https://m.example/api/box/pc"), ("GET", "https://m.example/api/box"),
                                     ("DELETE", "https://m.example/api/box/links/9")]
    assert all(s[2] == "t" * 43 for s in sent) and sent[0][3]["url"] == "https://a-b.trycloudflare.com"


# ---------- the server side (app.py) ----------

def phone_client(tmp_path, monkeypatch, with_bridge=True):
    from fastapi.testclient import TestClient

    from dubber import app
    from dubber.config import Settings

    monkeypatch.setattr(app.JobRunner, "_work", lambda self: None)  # jobs stay queued: nothing runs
    settings = Settings(work_dir=tmp_path / "w", output_dir=tmp_path / "out", env_file=tmp_path / ".env",
                        cookies_file=tmp_path / "cookies.txt")
    made = {}

    def factory(submit):
        made["bridge"] = phone.PhoneBridge(settings.env_file, 7860, submit, tools=tmp_path / "cf",
                                           mailbox=FakeMailbox())
        made["submit"] = submit
        return made["bridge"]

    c = TestClient(app.create_app(settings, runner=lambda *a, **k: None,
                                  phone_bridge=factory if with_bridge else None))
    return c, made, settings


ORIGIN = "https://dubber.example.workers.dev"
TUNNEL = {"host": "a-b.trycloudflare.com", "cf-ray": "8f00-WAW", "origin": ORIGIN}


def test_requests_through_the_tunnel_need_the_token(tmp_path, monkeypatch):
    c, made, _ = phone_client(tmp_path, monkeypatch)
    token = made["bridge"].token
    assert c.get("/api/videos").status_code == 200  # on this computer: as before
    assert c.get("/api/videos", headers=TUNNEL).status_code == 401
    assert c.get("/api/videos", headers={**TUNNEL, "X-Dubber-Token": "x" * 43}).status_code == 401
    ok = c.get("/api/videos", headers={**TUNNEL, "X-Dubber-Token": token})
    assert ok.status_code == 200 and ok.headers["access-control-allow-origin"] == ORIGIN
    assert c.get(f"/api/version?t={token}", headers=TUNNEL).status_code == 200  # <video>/<img>: token in the address
    other = c.get("/api/videos", headers={**TUNNEL, "origin": "https://evil.example", "X-Dubber-Token": token})
    assert "access-control-allow-origin" not in other.headers


def test_the_phone_may_only_dub_and_watch(tmp_path, monkeypatch):
    c, made, _ = phone_client(tmp_path, monkeypatch)
    h = {**TUNNEL, "X-Dubber-Token": made["bridge"].token}
    job = c.post("/api/jobs", headers=h, json={"url": "https://youtu.be/abc", "lang": "he"})
    assert job.status_code == 200
    assert c.get(f"/api/jobs/{job.json()['id']}", headers=h).status_code == 200
    assert c.post(f"/api/jobs/{job.json()['id']}/cancel", headers=h).status_code == 200
    for method, path in [("PUT", "/api/settings"), ("POST", "/api/settings/claude-key"), ("GET", "/api/cookies"),
                         ("POST", "/api/update"), ("GET", "/api/storage"), ("DELETE", "/api/storage/cache"),
                         ("POST", "/api/clone/install"), ("GET", "/api/phone"), ("GET", "/api/phone/qr"),
                         ("GET", "/"), ("GET", "/app.js")]:
        assert c.request(method, path, headers=h).status_code == 403, path
    preflight = c.options("/api/jobs", headers={**TUNNEL, "access-control-request-method": "POST"})
    assert preflight.status_code == 204 and "X-Dubber-Token" in preflight.headers["access-control-allow-headers"]


def test_tunnel_requests_are_refused_without_the_phone(tmp_path, monkeypatch):
    c, _, _ = phone_client(tmp_path, monkeypatch, with_bridge=False)
    assert c.get("/api/videos", headers=TUNNEL).status_code == 403
    assert c.get("/api/phone").json() == {"status": "off", "pair_url": None, "connected": False}


def test_phone_state_and_qr_code_on_this_computer(tmp_path, monkeypatch):
    c, made, _ = phone_client(tmp_path, monkeypatch)
    state = c.get("/api/phone").json()
    assert state["pair_url"] == f"{ORIGIN}/p/{made['bridge'].token}/"
    qr = c.get("/api/phone/qr")
    assert qr.headers["content-type"].startswith("image/svg+xml") and qr.text.startswith("<svg")


def test_links_left_by_a_phone_become_dubs(tmp_path, monkeypatch):
    c, made, _ = phone_client(tmp_path, monkeypatch)
    submit = made["submit"]
    submit({"id": "1", "url": "https://youtu.be/abc", "lang": "he", "voice": "female", "background": False})
    submit({"id": "2", "url": "https://youtu.be/abc"})  # the same link again while queued: skipped
    submit({"id": "3", "url": "not a link"})
    submit({"id": "4", "url": "https://youtu.be/def", "lang": "xx", "voice": "robot"})
    jobs = c.get("/api/jobs").json()
    assert sorted((j["url"], j["lang"], j["voice"], j["background"]) for j in jobs) == [
        ("https://youtu.be/abc", "he", "female", False), ("https://youtu.be/def", "ru", "male", True)]
