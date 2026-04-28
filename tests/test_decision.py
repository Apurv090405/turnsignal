from turnsignal.turntaking.decision import (
    Deadlines,
    extension_seconds,
    initial_deadline_ms,
    should_extend,
)
from turnsignal.turntaking.prosody_signal import ProsodyVerdict
from turnsignal.turntaking.semantic_signal import SemanticVerdict


D = Deadlines(fast_ms=200, default_ms=600, slow_ms=1200)


def test_initial_deadline_ending_is_fast():
    assert initial_deadline_ms(ProsodyVerdict.ENDING, D) == 200
#----------#


def test_initial_deadline_going_is_slow():
    assert initial_deadline_ms(ProsodyVerdict.GOING, D) == 1200
#----------#


def test_initial_deadline_ambiguous_is_default():
    assert initial_deadline_ms(ProsodyVerdict.AMBIGUOUS, D) == 600
#----------#


def test_should_extend_only_when_ending_and_incomplete():
    assert should_extend(ProsodyVerdict.ENDING, SemanticVerdict.INCOMPLETE) is True
    assert should_extend(ProsodyVerdict.ENDING, SemanticVerdict.COMPLETE) is False
    assert should_extend(ProsodyVerdict.ENDING, None) is False
    assert should_extend(ProsodyVerdict.GOING, SemanticVerdict.INCOMPLETE) is False
    assert should_extend(ProsodyVerdict.AMBIGUOUS, SemanticVerdict.INCOMPLETE) is False
#----------#


def test_extension_seconds_from_fast_to_slow():
    assert extension_seconds(200, D) == (1200 - 200) / 1000
#----------#


def test_extension_seconds_when_already_at_slow():
    assert extension_seconds(1200, D) == 0.0
#----------#


def test_extension_seconds_never_negative():
    assert extension_seconds(2000, D) == 0.0
#----------#
