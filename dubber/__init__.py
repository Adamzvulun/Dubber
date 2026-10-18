"""Dubber: turn an English YouTube video into a Russian-dubbed one."""

import os

__version__ = "0.6.1"

# Hugging Face's newer "Xet" downloader failed on a real Windows PC ("CAS Client Error ... error sending request")
# where plain HTTPS works; use plain HTTPS unless the user chose otherwise. Must be set before huggingface_hub loads.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
