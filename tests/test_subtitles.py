from dubber.segments import Segment
from dubber.subtitles import srt_timestamp, to_bilingual, to_srt, to_transcript, write_all

SEGS = [Segment(0.5, 2.25, "Hello.", "Привет."), Segment(61.0, 3725.5, "Bye.", "Пока.")]


def test_srt_timestamp():
    assert srt_timestamp(0) == "00:00:00,000"
    assert srt_timestamp(3725.5) == "01:02:05,500"


def test_to_srt_russian_and_english():
    ru = to_srt(SEGS)
    assert ru.startswith("1\n00:00:00,500 --> 00:00:02,250\nПривет.\n")
    assert "2\n00:01:01,000 --> 01:02:05,500\nПока." in ru
    assert "Hello." in to_srt(SEGS, russian=False)


def test_srt_skips_empty_lines():
    assert to_srt([Segment(0, 1, "x", ""), Segment(1, 2, "y", "у")]).startswith("1\n00:00:01,000")


def test_transcripts(tmp_path):
    text = to_transcript(SEGS, "Title")
    assert text.startswith("Title\n\n[00:00] Привет.")
    assert "[01:01] Пока." in text
    assert "EN: Hello." in to_bilingual(SEGS) and "RU: Привет." in to_bilingual(SEGS)
    files = write_all(SEGS, tmp_path / "out", "Title")
    assert files["ru_srt"].read_text(encoding="utf-8") == to_srt(SEGS)
