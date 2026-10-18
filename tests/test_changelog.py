"""The "What's new" note: every release lists its changes in RU and EN (dubber/changelog.json)."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from dubber import __version__, app
from dubber.config import Settings

CHANGELOG = Path(app.__file__).with_name("changelog.json")


def test_every_release_has_its_changes_in_both_languages():
    log = json.loads(CHANGELOG.read_text(encoding="utf-8"))
    assert __version__ in log, "add this version's changes to dubber/changelog.json"
    for version, notes in log.items():
        assert notes["ru"] and len(notes["ru"]) == len(notes["en"]), version


def test_changelog_api_newest_first(tmp_path):
    settings = Settings(work_dir=tmp_path / "w", output_dir=tmp_path / "out")
    versions = [entry["version"] for entry in TestClient(app.create_app(settings)).get("/api/changelog").json()]
    assert versions[0] == __version__ and versions == sorted(versions, key=lambda v: tuple(map(int, v.split("."))),
                                                             reverse=True)
