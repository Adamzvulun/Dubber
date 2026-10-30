"""Who says each line (speakers.py), with stand-in voice prints; the real model is checked by hand (RESEARCH)."""

import numpy as np

from dubber import speakers
from dubber.segments import Segment


def unit(*v):
    v = np.array(v, dtype=np.float32)
    return v / np.linalg.norm(v)


def test_lines_with_matching_voice_prints_are_one_speaker():
    a, b, c = unit(1, 0, 0), unit(0, 1, 0), unit(0, 0, 1)
    near_a = unit(1, 0.3, 0)  # the same voice, a little different (cos 0.96)
    prints = [a, b, near_a, c, b, a]
    assert speakers.group(prints, [2.0] * 6) == [0, 1, 0, 2, 1, 0]  # numbered in order of first appearance


def test_a_short_line_joins_the_closest_speaker_but_never_starts_one():
    a, b = unit(1, 0, 0), unit(0, 1, 0)
    prints = [a, b, unit(0.2, 1, 0.9), a]  # line 2 is short (0.5 s): its print is unreliable
    assert speakers.group(prints, [2.0, 2.0, 0.5, 2.0]) == [0, 1, 1, 0]
    assert speakers.group([unit(1, 0, 0)], [0.4]) == [None]  # nobody to join


def test_no_print_no_speaker():
    a = unit(1, 0, 0)
    assert speakers.group([a, None, a], [2.0, 2.0, 2.0]) == [0, None, 0]


class FakeExtractor:
    """Gives each line the voice print of whoever "speaks" at that time (a tone's pitch stands for the voice)."""

    def __init__(self, who):
        self.who, self.calls = who, []

    def __call__(self, samples, start, end):
        self.calls.append((start, end))
        return unit(*[1.0 if k == self.who(start) else 0.0 for k in range(3)])


def test_assign_reads_each_line_from_the_voice_track(tmp_path):
    lines = [Segment(0.0, 2.0, "a", "а"), Segment(2.5, 4.0, "b", "б"), Segment(4.5, 6.0, "c", "в"),
             Segment(6.5, 6.6, "d", "г")]
    who = lambda t: 0 if t < 2.4 or t > 4.4 else 1  # noqa: E731
    extractor = FakeExtractor(who)
    samples = np.zeros(16000 * 7, dtype=np.float32)
    # line 3 is too short for a voice print: it goes with the nearest line in time
    assert speakers.assign(lines, samples, extractor) == [0, 1, 0, 0]
    assert len(extractor.calls) == 3
