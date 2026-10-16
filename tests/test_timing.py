from dubber.segments import Segment
from dubber.timing import edge_rate, plan_rates, slots


def segs(*spans):
    return [Segment(a, b, "en", "ру") for a, b in spans]


def test_slots_use_the_pause_after_a_line():
    s = slots(segs((0.0, 2.0), (3.0, 4.0)))
    assert abs(s[0] - 2.85) < 1e-9  # until 0.15 s before the next line
    assert abs(s[1] - 2.0) < 1e-9  # last line: its speech + 1 s tail


def test_steady_pace_follows_the_speaker():
    # Russian is 1.4x longer on every line -> every line at 1.4, no jumps.
    lines = segs((0, 4), (5, 9), (10, 14))
    rates = plan_rates(lines, [5.6, 5.6, 5.6], max_rate=1.6)
    assert all(abs(r - 1.4) < 1e-9 for r in rates)


def test_one_long_line_does_not_make_the_pace_jump():
    # Middle line is longer (1.65x vs 1.4x elsewhere) and the next line follows closely: it must speed up
    # to fit, and its neighbours are lifted so the pace changes by at most STEP between lines.
    lines = segs((0, 4), (4.5, 8.5), (9.0, 13.0), (13.5, 17.5))
    rates = plan_rates(lines, [5.6, 6.6, 5.6, 5.6], max_rate=1.6)
    assert rates[1] >= 6.6 / (9.0 - 0.15 - 4.5) - 1e-9  # fits before the next line
    assert all(abs(a - b) <= 0.08 + 1e-9 for a, b in zip(rates, rates[1:], strict=False))
    assert all(r <= 1.6 for r in rates)


def test_rates_are_capped_and_short_russian_slows_only_a_little():
    assert plan_rates(segs((0, 2)), [8.0], max_rate=1.6) == [1.6]
    assert plan_rates(segs((0, 4)), [2.0], max_rate=1.6) == [0.9]
    assert plan_rates(segs((0, 4)), [None], max_rate=1.6) == [1.0]


def test_edge_rate_strings():
    assert edge_rate(1.0) == "+0%" and edge_rate(1.347) == "+35%" and edge_rate(0.9) == "-10%"
