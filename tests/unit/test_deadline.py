import time

from rm_core.deadline import Deadline


def test_remaining_shrinks_and_never_goes_negative() -> None:
    d = Deadline.after(0.05)
    assert 0 < d.remaining() <= 0.05
    assert not d.expired
    time.sleep(0.06)
    assert d.remaining() == 0.0
    assert d.expired


def test_cap_never_exceeds_what_is_left() -> None:
    d = Deadline.after(5)
    assert d.cap(30) <= 5
    assert d.cap(1) == 1
