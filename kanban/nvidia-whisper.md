---
id: 35
status: review
priority: High
blocked_by: []
tags: [bug, nvidia, whisper, v0.10.1]
---

# Dubbing fails on PCs with an NVIDIA card: "cublas64_12.dll is not found"

Adam (2026-10-29): 0.10.0 on a new computer, an Instagram reel into Hebrew → «Something went wrong… Library
cublas64_12.dll is not found or cannot be loaded». The download worked; Whisper (device "auto") picked the NVIDIA
card, whose cuBLAS/cuDNN libraries are not installed. Adam chose: never fail, and fetch NVIDIA's files automatically.

## Narrative
- 2026-10-29: Fix in 0.10.1 (ADR-034): CPU fallback in `transcribe.py` (remembered per run), `dubber/gpu.py`
  installs `nvidia-cublas-cu12` + `nvidia-cudnn-cu12` in the background on Windows NVIDIA PCs and puts their DLL
  folders on the search path; clear message if the card still fails. Unit tests; Windows CI checks the wheels
  resolve. Not verified on a real NVIDIA card. (by @claude)
