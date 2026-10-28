from dubber import deps


def test_requirements_read_from_pyproject(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "x"\ndependencies = [\n    "yt-dlp[default]>=2025.10.1",\n'
                         '    "requests>=2.31",  # comment\n    "numpy",\n]\n\n[project.optional-dependencies]\n'
                         'dev = ["pytest>=8"]\n', encoding="utf-8")
    assert deps.requirements(pyproject) == [("yt-dlp", "2025.10.1"), ("requests", "2.31"), ("numpy", None)]


def test_the_real_pyproject_lists_the_core_components():
    names = [name for name, _ in deps.requirements()]
    assert {"faster-whisper", "onnxruntime", "fastapi", "edge-tts"} <= set(names)
    assert "pytest" not in names  # dev extras are not needed to run


def test_missing_and_too_old_components():
    found = deps.missing([("numpy", "1.0"), ("dubber-no-such-package", None), ("numpy", "999.0")])
    assert found[0] == "dubber-no-such-package"
    assert found[1].startswith("numpy>=999.0 (installed ")
    assert len(found) == 2


def test_this_environment_is_complete():
    assert deps.missing() == []
    assert deps.broken() == []


def test_a_module_that_fails_to_load_is_reported():
    assert deps.broken(("json", "dubber_no_such_module")) == ["dubber_no_such_module: No module named "
                                                              "'dubber_no_such_module'"]


def test_main_exit_codes(monkeypatch, capsys):
    monkeypatch.setattr(deps, "missing", lambda: ["anthropic"])
    assert deps.main() == 1
    assert capsys.readouterr().out.strip() == "anthropic"
    monkeypatch.setattr(deps, "missing", lambda: [])
    monkeypatch.setattr(deps, "broken", lambda: ["onnxruntime: DLL load failed"])
    assert deps.main() == 2
    monkeypatch.setattr(deps, "broken", lambda: [])
    assert deps.main() == 0


def test_extras_we_ask_for_are_checked_too(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\ndependencies = [\n    # a comment with "quotes"\n'
                         '    "yt-dlp[default,curl-cffi]>=2026.10.21",\n]\n', encoding="utf-8")
    assert deps.requirements(pyproject) == [("yt-dlp", "2026.10.21")]
    extras = deps.extra_components(pyproject)
    assert "curl-cffi" in extras  # what lets TikTok and Instagram download without a login
    assert "pytest" not in extras


def test_browser_impersonation_is_available():
    import yt_dlp

    with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
        from yt_dlp.networking.impersonate import ImpersonateTarget

        assert ydl._impersonate_target_available(ImpersonateTarget("chrome"))
