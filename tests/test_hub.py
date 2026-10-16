import os

import pytest

import dubber  # noqa: F401  (sets the Hugging Face download defaults)
from dubber.hub import retry


def test_plain_https_downloads_by_default():
    assert os.environ.get("HF_HUB_DISABLE_XET") == "1"


def test_retry_recovers_from_a_dropped_download():
    calls, waits = [], []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("CAS Client Error: error sending request")
        return "model"

    assert retry(flaky, sleep=waits.append) == "model"
    assert len(calls) == 3 and waits == [5.0, 10.0]


def test_retry_gives_up_with_the_last_error():
    def broken():
        raise OSError("no internet")

    with pytest.raises(OSError):
        retry(broken, attempts=2, sleep=lambda s: None)
