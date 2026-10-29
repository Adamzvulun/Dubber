import os
import subprocess

from dubber import app, gpu, transcribe


def test_wanted_only_on_windows_with_an_nvidia_card(monkeypatch):
    monkeypatch.setattr(gpu, "installed", lambda: False)
    monkeypatch.delenv("DUBBER_DEVICE", raising=False)
    card = {"name": "NVIDIA GeForce RTX 3070", "vram_gb": 8.0}
    assert gpu.wanted("win32", lambda: card)
    assert not gpu.wanted("win32", lambda: None)  # no card or no driver
    assert not gpu.wanted("linux", lambda: card)
    monkeypatch.setenv("DUBBER_DEVICE", "cpu")
    assert not gpu.wanted("win32", lambda: card)
    monkeypatch.delenv("DUBBER_DEVICE")
    monkeypatch.setattr(gpu, "installed", lambda: True)
    assert not gpu.wanted("win32", lambda: card)


def test_dll_folders_are_put_on_the_search_path(tmp_path, monkeypatch):
    (tmp_path / "nvidia" / "cublas" / "bin").mkdir(parents=True)
    added = []
    monkeypatch.setattr(os, "add_dll_directory", lambda d: added.append(d) or object(), raising=False)
    monkeypatch.setenv("PATH", "/usr/bin")
    dirs = gpu.use_dll_dirs(tmp_path, system="win32")
    assert dirs == [tmp_path / "nvidia" / "cublas" / "bin"]  # cudnn not installed: not added
    assert os.environ["PATH"].startswith(str(dirs[0]) + os.pathsep) and added == [str(dirs[0])]
    gpu.use_dll_dirs(tmp_path, system="win32")
    assert os.environ["PATH"].count(str(dirs[0])) == 1
    assert gpu.use_dll_dirs(tmp_path, system="linux") == []


def test_installer_runs_pip_and_lets_the_card_be_tried_again(tmp_path, monkeypatch, capsys):
    ran = []

    def run(cmd, **kw):
        ran.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(gpu, "use_dll_dirs", lambda: [])
    monkeypatch.setattr(transcribe, "_gpu_failed", True)
    installer = gpu.Installer(tmp_path / "w" / "gpu-install.log", python="py", run=run)
    assert installer.install() is True
    assert ran == [["py", "-m", "pip", "install", "--disable-pip-version-check", *gpu.PACKAGES]]
    assert transcribe._gpu_failed is False and "готова" in capsys.readouterr().out
    assert "nvidia-cublas-cu12" in (tmp_path / "w" / "gpu-install.log").read_text(encoding="utf-8")


def test_installer_failure_only_logs(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(transcribe, "_gpu_failed", True)
    installer = gpu.Installer(tmp_path / "gpu-install.log", run=lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1))
    assert installer.install() is False and installer.done.is_set()
    assert transcribe._gpu_failed is True and "процессоре" in capsys.readouterr().out
    gone = gpu.Installer(tmp_path / "x.log", python="/no/such/python")
    assert gone.install() is False


def test_gpu_errors_get_a_clear_message():
    message = app.friendly_error(RuntimeError("Library cublas64_12.dll is not found or cannot be loaded"))
    assert "Видеокарта NVIDIA" in message and "Подробности" not in message
    assert "NVIDIA graphics card" in app.friendly_error(RuntimeError("cudnn64_9.dll missing"), "en")
