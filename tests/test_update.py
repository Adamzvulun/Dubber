"""Self-update from GitHub `main` (dubber/update.py) and its use at start and on the website. No network."""

import io
import zipfile
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from dubber import __version__, app, update
from dubber.config import Settings

RAW = "https://raw.githubusercontent.com/Adamzvulun/Dubber/main/dubber/__init__.py"
ZIP = "https://codeload.github.com/Adamzvulun/Dubber/zip/refs/heads/main"


def github_zip(files: dict[str, str]) -> bytes:
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        archive.writestr("Dubber-main/", "")
        for name, text in files.items():
            archive.writestr(f"Dubber-main/{name}", text)
    return data.getvalue()


def make_updater(root, responses, runs=None):
    def fetch(url, timeout):
        if isinstance(responses.get(url), Exception) or url not in responses:
            raise responses.get(url, OSError("offline"))
        return responses[url]

    runs = [] if runs is None else runs
    return update.Updater(root, fetch=fetch, run=lambda cmd, **k: runs.append(cmd) or SimpleNamespace(returncode=0),
                          python="python")


NEW = {"dubber/__init__.py": '__version__ = "9.0.0"\n', "pyproject.toml": "[project]\nversion = \"9.0.0\"\n",
       "dubber/app.py": "new app", "scripts/start_windows.bat": "new start"}


@pytest.fixture
def installed(tmp_path):
    """A PC with an older version: program files from the last update, plus the user's own data."""
    files = {"dubber/__init__.py": '__version__ = "0.4.0"\n', "pyproject.toml": "[project]\nversion = \"0.4.0\"\n",
             "dubber/app.py": "old app", "dubber/dropped.py": "removed in the new version",
             ".env": "DUBBER_CLAUDE_KEY=sk-ant-mine", "glossary.txt": "мой глоссарий",
             "output/vid--ru-abc/meta.json": "{}", "work/vid/source.mp4": "video"}
    for name, text in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text, encoding="utf-8")
    (tmp_path / update.MANIFEST).write_text("dubber/__init__.py\ndubber/app.py\ndubber/dropped.py\npyproject.toml\n")
    return tmp_path


def test_latest_version_and_comparison(tmp_path):
    assert make_updater(tmp_path, {RAW: b'"""x"""\n__version__ = "0.10.0"\n'}).latest() == "0.10.0"
    assert make_updater(tmp_path, {}).latest() is None  # offline: start as usual
    assert update.is_newer("0.10.0", "0.9.3") and not update.is_newer("0.4.1", "0.4.1")
    assert not update.is_newer(None, "0.4.1")


def test_install_replaces_program_files_and_keeps_user_data(installed):
    hostile = {**NEW, ".env": "stolen", "output/vid--ru-abc/meta.json": "overwritten"}
    runs = []
    updater = make_updater(installed, {ZIP: github_zip(hostile)}, runs)
    assert updater.install() == "9.0.0"

    assert (installed / "dubber/app.py").read_text() == "new app"
    assert (installed / "scripts/start_windows.bat").read_text() == "new start"
    assert not (installed / "dubber/dropped.py").exists()  # listed by the last update, gone from main
    assert (installed / ".env").read_text() == "DUBBER_CLAUDE_KEY=sk-ant-mine"
    assert (installed / "glossary.txt").read_text(encoding="utf-8") == "мой глоссарий"
    assert (installed / "output/vid--ru-abc/meta.json").read_text() == "{}"
    assert (installed / "work/vid/source.mp4").exists()
    assert set((installed / update.MANIFEST).read_text().split()) == set(NEW)
    assert not list(installed.rglob("*.partial"))
    # pyproject changed → components reinstalled like install_windows.bat does; yt-dlp is refreshed every time
    assert runs[0][-3:] == ["--no-build-isolation", "-e", "."] and runs[-1][-1] == "yt-dlp"

    runs.clear()
    updater.install()  # same version again: pyproject unchanged → no reinstall
    assert len(runs) == 1 and runs[0][-1] == "yt-dlp"


def test_first_update_after_a_zip_install_deletes_nothing(installed):
    (installed / update.MANIFEST).unlink()
    make_updater(installed, {ZIP: github_zip(NEW)}).install()
    assert (installed / "dubber/dropped.py").exists()


@pytest.mark.parametrize("download", [b"not a zip", github_zip({"README.md": "x"}), OSError("offline")])
def test_a_bad_download_changes_nothing(installed, download):
    with pytest.raises(update.UpdateError):
        make_updater(installed, {ZIP: download}).install()
    assert (installed / "dubber/app.py").read_text() == "old app"


def test_failed_component_install_is_reported(installed):
    updater = make_updater(installed, {ZIP: github_zip(NEW)})
    updater.run = lambda cmd, **k: SimpleNamespace(returncode=1)
    with pytest.raises(update.UpdateError):
        updater.install()


def test_off_in_a_git_checkout_or_by_setting(tmp_path, monkeypatch):
    updater = make_updater(tmp_path, {})
    assert updater.enabled()
    monkeypatch.setenv("DUBBER_AUTO_UPDATE", "0")
    assert not updater.enabled()
    monkeypatch.delenv("DUBBER_AUTO_UPDATE")
    (tmp_path / ".git").mkdir()
    assert not updater.enabled()


class FakeUpdater:
    def __init__(self, latest, fail=False):
        self.latest_version, self.fail, self.installs, self.checks = latest, fail, 0, 0

    def enabled(self):
        return True

    def latest(self, timeout=5.0):
        self.checks += 1
        return self.latest_version

    def install(self, timeout=120.0):
        self.installs += 1
        if self.fail:
            raise update.UpdateError("offline")
        return self.latest_version


def test_update_at_start(monkeypatch):
    monkeypatch.delenv("DUBBER_JUST_UPDATED", raising=False)
    assert not app.update_at_start(FakeUpdater(__version__))  # up to date
    newer = FakeUpdater("99.0.0")
    assert app.update_at_start(newer) and newer.installs == 1
    assert not app.update_at_start(FakeUpdater("99.0.0", fail=True))  # start the current version anyway
    monkeypatch.setenv("DUBBER_JUST_UPDATED", "1")  # the freshly started new version doesn't check again
    assert not app.update_at_start(FakeUpdater("99.0.0"))


def client(tmp_path, updater, restart=None, runner=None):
    settings = Settings(work_dir=tmp_path / "w", output_dir=tmp_path / "out")
    site = app.create_app(settings, runner=runner or (lambda *a, **k: None), updater=updater, restart=restart)
    return TestClient(site)


def test_website_offers_and_installs_an_update(tmp_path):
    restarts = []
    fake = FakeUpdater("99.0.0")
    c = client(tmp_path, fake, restart=lambda: restarts.append(1))
    state = c.get("/api/update").json()
    assert state == {"current": __version__, "latest": "99.0.0", "enabled": True, "available": True}
    c.get("/api/update")
    assert fake.checks == 1  # GitHub is asked at most once an hour

    assert c.post("/api/update", headers={"Origin": "https://evil.example"}).status_code == 403
    assert c.post("/api/update").json() == {"installed": "99.0.0", "restarting": True}
    import time
    for _ in range(50):
        if restarts:
            break
        time.sleep(0.05)
    assert restarts == [1]


def test_website_update_refused_when_none_or_while_dubbing(tmp_path):
    assert client(tmp_path, FakeUpdater(__version__)).post("/api/update").status_code == 409

    import threading
    release = threading.Event()
    c = client(tmp_path, FakeUpdater("99.0.0"), runner=lambda *a, **k: release.wait(5))
    c.post("/api/jobs", json={"url": "https://youtu.be/x"})
    r = c.post("/api/update")
    release.set()
    assert r.status_code == 409 and "озвучки" in r.json()["detail"]["ru"]

    failing = FakeUpdater("99.0.0", fail=True)
    assert client(tmp_path, failing).post("/api/update").status_code == 502


def test_failed_component_install_keeps_the_old_version_and_retries_next_time(installed):
    # QA: pip failing after the files were replaced left the new version number on disk, so no later start retried.
    runs = []
    updater = make_updater(installed, {ZIP: github_zip(NEW)}, runs)
    updater.run = lambda cmd, **k: runs.append(cmd) or SimpleNamespace(returncode=1 if "-e" in cmd else 0)
    with pytest.raises(update.UpdateError):
        updater.install()
    assert '"0.4.0"' in (installed / "dubber/__init__.py").read_text()  # still the old version → retried
    updater.run = lambda cmd, **k: runs.append(cmd) or SimpleNamespace(returncode=0)
    runs.clear()
    assert updater.install() == "9.0.0"
    assert any("-e" in cmd for cmd in runs)  # the components are installed although pyproject is already new
    assert '"9.0.0"' in (installed / "dubber/__init__.py").read_text()


def test_a_locked_file_is_an_update_error_and_leaves_the_old_version(installed, monkeypatch):
    # Windows: antivirus or an open editor can lock a file while it is replaced.
    real_replace = update.Path.replace

    def replace(self, target):
        if str(target).endswith("app.py"):
            raise PermissionError("locked")
        return real_replace(self, target)

    monkeypatch.setattr(update.Path, "replace", replace)
    with pytest.raises(update.UpdateError):
        make_updater(installed, {ZIP: github_zip(NEW)}).install()
    assert '"0.4.0"' in (installed / "dubber/__init__.py").read_text()
    assert not list(installed.rglob("*.partial"))


def test_paths_outside_the_program_folder_are_ignored(installed, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside") / "victim.txt"
    outside.write_text("keep")
    (installed / update.MANIFEST).write_text(f"../{outside.parent.name}/victim.txt\n{outside}\n")
    hostile = {**NEW, "..\\..\\evil.txt": "x", "C:/evil.txt": "x"}
    make_updater(installed, {ZIP: github_zip(hostile)}).install()
    assert outside.read_text() == "keep"
    assert not (installed.parent / "evil.txt").exists()
    assert set((installed / update.MANIFEST).read_text().split()) == set(NEW)


def test_only_one_update_at_a_time_and_no_new_dub_meanwhile(tmp_path):
    import threading
    started, release = threading.Event(), threading.Event()

    class SlowUpdater(FakeUpdater):
        def install(self, timeout=120.0):
            started.set()
            release.wait(5)
            return super().install(timeout)

    c = client(tmp_path, SlowUpdater("99.0.0"))
    first = threading.Thread(target=lambda: c.post("/api/update"))
    first.start()
    assert started.wait(5)
    assert c.post("/api/update").status_code == 409
    r = c.post("/api/jobs", json={"url": "https://youtu.be/x"})
    assert r.status_code == 409 and "обнов" in r.json()["detail"]["ru"]
    release.set()
    first.join(5)
