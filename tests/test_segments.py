from dubber.segments import Segment, load_segments, merge_into_sentences, save_segments


def test_merge_joins_unfinished_sentences():
    segs = [Segment(0, 2, "So today we"), Segment(2.1, 4, "talk about tests."), Segment(4.2, 6, "Next topic.")]
    merged = merge_into_sentences(segs)
    assert [s.text for s in merged] == ["So today we talk about tests.", "Next topic."]
    assert (merged[0].start, merged[0].end) == (0, 4)


def test_merge_respects_gap_and_max_duration():
    segs = [Segment(0, 2, "one"), Segment(5, 6, "two")]  # long pause
    assert len(merge_into_sentences(segs)) == 2
    segs = [Segment(0, 10, "long"), Segment(10.1, 14, "more")]  # would exceed 12 s
    assert len(merge_into_sentences(segs)) == 2


def test_merge_drops_empty_and_roundtrips(tmp_path):
    merged = merge_into_sentences([Segment(0, 1, "  "), Segment(1, 2, "Hi.")])
    assert [s.text for s in merged] == ["Hi."]
    path = tmp_path / "s.json"
    merged[0].ru = "Привет."
    save_segments(merged, path)
    assert load_segments(path) == merged
