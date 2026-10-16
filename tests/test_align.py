from dubber.align import SAMPLE_RATE, atempo_filter, build_track, plan_speed
from dubber.media import decode_audio, duration
from dubber.segments import Segment


def test_plan_speed():
    assert plan_speed(2.0, 3.0, 1.5) == 1.0
    assert plan_speed(3.0, 2.0, 1.5) == 1.5
    assert abs(plan_speed(2.4, 2.0, 1.5) - 1.2) < 1e-9
    assert atempo_filter(1.0) is None and atempo_filter(1.25) == "atempo=1.2500"


def test_build_track_places_and_fits_clips(tmp_path, tone):
    segs = [Segment(1.0, 2.0, "a", "а"), Segment(3.0, 4.0, "b", "б"), Segment(5.0, 5.5, "c", "")]
    clips = [tone(tmp_path / "0.wav", 1.5), tone(tmp_path / "1.wav", 0.5), None]
    out = build_track(segs, clips, total_seconds=6.0, out_wav=tmp_path / "track.wav")
    assert abs(duration(out) - 6.0) < 0.05
    audio = decode_audio(out, SAMPLE_RATE)
    energy = lambda a, b: float(abs(audio[int(a * SAMPLE_RATE):int(b * SAMPLE_RATE)]).mean())  # noqa: E731
    assert energy(0.0, 0.9) < 1e-3  # silence before first segment
    assert energy(1.1, 2.4) > 0.03  # first clip (1.5 s fits its 2 s slot unchanged)
    assert energy(2.6, 2.9) < 1e-3  # gap
    assert energy(3.05, 3.45) > 0.03  # second clip
    assert energy(3.6, 6.0) < 1e-3  # nothing for empty third segment


def test_build_track_corrects_a_little_then_pushes_back(tmp_path, tone):
    segs = [Segment(0.0, 1.0, "a", "а"), Segment(2.0, 3.0, "b", "б")]
    clips = [tone(tmp_path / "0.wav", 2.4), tone(tmp_path / "1.wav", 0.5)]
    report = []
    out = build_track(segs, clips, 4.0, tmp_path / "t.wav", report=report)
    audio = decode_audio(out, SAMPLE_RATE)
    # Slot = 2.0 - 0.15 s breath = 1.85 s; the 2.4 s clip may only be stretched 1.1x -> ~2.18 s,
    # so the second line starts ~0.18 s late instead of overlapping.
    assert report[0]["stretch"] == 1.1 and report[0]["delay"] == 0.0
    assert 0.1 < report[1]["delay"] < 0.25
    assert float(abs(audio[int(2.25 * SAMPLE_RATE):int(2.6 * SAMPLE_RATE)]).mean()) > 0.03


def test_silence_around_a_clip_is_trimmed(tmp_path, tone):
    import numpy as np

    from dubber.align import speech_seconds, trim_silence

    padded = tmp_path / "padded.wav"
    import subprocess

    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(tone(tmp_path / "t.wav", 1.0)),
                    "-af", "adelay=250,apad=pad_dur=0.9", str(padded)], check=True)
    assert abs(duration(padded) - 2.15) < 0.05
    assert abs(speech_seconds(padded) - 1.06) < 0.03  # 1 s of speech + 2 x 0.03 s pad
    assert len(trim_silence(np.zeros(100, dtype=np.float32))) == 0
