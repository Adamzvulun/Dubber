import pytest

from dubber.download import base_opts, is_url


def test_is_url():
    assert is_url("https://youtu.be/x") and not is_url("C:/videos/a.mp4")


def test_cookies_option(tmp_path, monkeypatch):
    monkeypatch.delenv("DUBBER_COOKIES", raising=False)
    assert "cookiefile" not in base_opts()
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n")
    monkeypatch.setenv("DUBBER_COOKIES", str(cookies))
    assert base_opts()["cookiefile"] == str(cookies)
    monkeypatch.setenv("DUBBER_COOKIES", str(tmp_path / "missing.txt"))
    with pytest.raises(FileNotFoundError):
        base_opts()
