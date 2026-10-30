import os
import subprocess
from pathlib import Path

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
    monkeypatch.setattr(gpu, "ort_ready", lambda ort_dir=None: True)  # voice removal's part: its own test below
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


METADATA = """Metadata-Version: 2.1
Name: onnxruntime-gpu
Requires-Dist: numpy>=1.21.6
Provides-Extra: cuda
Requires-Dist: nvidia-cuda-runtime~=13.0; extra == "cuda"
Requires-Dist: nvidia-cufft~=12.0; extra == "cuda"
Provides-Extra: cudnn
Requires-Dist: nvidia-cudnn-cu13~=9.0; extra == "cudnn"
Requires-Dist: ml_dtypes; extra == "quantization"
"""


def test_voice_removal_gets_onnxruntime_gpu_and_its_cuda_libraries_in_their_own_folder(tmp_path, monkeypatch, capsys):
    """ADR-045: onnxruntime-gpu (same version as onnxruntime) with --no-deps, then the NVIDIA wheels its cuda/cudnn
    extras name (not numpy etc.: the program's own are used), all into one folder that appears only when complete."""
    ran = []

    def run(cmd, **kw):
        ran.append(cmd)
        target = Path(cmd[cmd.index("--target") + 1])
        if "--no-deps" in cmd:
            info = target / "onnxruntime_gpu-1.31.1.dist-info"
            info.mkdir(parents=True)
            (info / "METADATA").write_text(METADATA, encoding="utf-8")
            (target / "onnxruntime" / "capi").mkdir(parents=True)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(gpu, "_ort_version", lambda: "1.31.1")
    monkeypatch.delenv("DUBBER_DEVICE", raising=False)
    ort = tmp_path / "venv" / "onnxruntime-gpu"
    ort.parent.mkdir()
    installer = gpu.Installer(tmp_path / "gpu-install.log", python="py", run=run, ort_dir=ort)
    assert installer.install_ort() is True
    assert "onnxruntime-gpu==1.31.1" in ran[0] and "--no-deps" in ran[0]
    assert ran[1][-3:] == ["nvidia-cuda-runtime~=13.0", "nvidia-cufft~=12.0", "nvidia-cudnn-cu13~=9.0"]
    assert gpu.ort_ready(ort) and not (tmp_path / "venv" / "onnxruntime-gpu.partial").exists()

    failing = gpu.Installer(tmp_path / "gpu-install.log", python="py",
                            run=lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1), ort_dir=tmp_path / "v2" / "o")
    (tmp_path / "v2").mkdir()
    assert failing.install_ort() is False
    assert (tmp_path / "v2" / "onnxruntime-gpu-failed-1.31.1").exists()  # not retried at every start
    assert not (tmp_path / "v2" / "o").exists()


def test_the_card_is_not_asked_for_when_the_user_chose_the_processor(tmp_path, monkeypatch):
    (tmp_path / "onnxruntime" / "capi").mkdir(parents=True)
    monkeypatch.delenv("DUBBER_DEVICE", raising=False)
    assert gpu.ort_ready(tmp_path)
    monkeypatch.setenv("DUBBER_DEVICE", "cpu")
    assert not gpu.ort_ready(tmp_path)
