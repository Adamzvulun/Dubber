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


def _words(spec):
    """spec: list of (start, end, text)."""
    from dubber.segments import Word

    return [Word(a, b, f" {t}") for a, b, t in spec]


def test_units_are_sentences_with_speech_only_bounds():
    from dubber.segments import split_into_units

    words = _words([(0.5, 0.8, "Hi"), (0.9, 1.2, "there."), (1.3, 1.6, "How"), (1.7, 2.0, "are"), (2.1, 2.5, "you?")])
    units = split_into_units(words)
    assert [(u.start, u.end, u.text) for u in units] == [(0.5, 1.2, "Hi there."), (1.3, 2.5, "How are you?")]


def test_units_split_at_a_long_pause_and_save_without_words(tmp_path):
    from dubber.segments import load_segments, save_segments, split_into_units

    units = split_into_units(_words([(0, 0.5, "So"), (0.6, 1.0, "basically"), (2.5, 3.0, "we"), (3.1, 3.5, "won.")]))
    assert [u.text for u in units] == ["So basically", "we won."]
    save_segments(units, tmp_path / "s.json")
    assert "words" not in (tmp_path / "s.json").read_text(encoding="utf-8")
    assert load_segments(tmp_path / "s.json")[1].text == "we won."


def test_long_sentence_splits_at_its_best_break():
    from dubber.segments import split_into_units

    # 14 s sentence; a comma + 0.5 s pause at 6 s is the natural place to cut.
    spec = [(t, t + 0.4, "word") for t in [0.0, 1.0, 2.0, 3.0, 4.0]] + [(5.0, 5.5, "point,")]
    spec += [(6.0 + t, 6.4 + t, "more") for t in range(7)] + [(13.5, 14.0, "end.")]
    units = split_into_units(_words(spec), max_duration=10.0)
    assert len(units) == 2 and units[0].text.endswith("point,") and units[1].start == 6.0


def test_non_speech_is_not_a_line():
    from dubber.segments import split_into_units

    units = split_into_units(_words([(0.0, 1.0, "♪"), (1.0, 2.0, "[Music]"), (2.0, 2.4, "Hello"), (2.5, 2.9, "all."),
                                     (4.5, 5.0, "♪♪"), (6.0, 6.5, "...")]))
    assert [(u.start, u.end, u.text) for u in units] == [(2.0, 2.9, "Hello all.")]


def test_a_line_never_mixes_spoken_languages():
    from dubber.segments import Word, split_into_units

    words = [Word(0.0, 0.4, " Let's", "en"), Word(0.5, 0.9, " hear", "en"), Word(1.0, 1.3, " her", "en"),
             Word(1.5, 1.9, " Bonjour", "fr"), Word(2.0, 2.4, " à", "fr"), Word(2.5, 2.9, " tous.", "fr")]
    units = split_into_units(words)
    assert [(u.text, u.lang) for u in units] == [("Let's hear her", "en"), ("Bonjour à tous.", "fr")]
