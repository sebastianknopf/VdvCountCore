from datetime import timedelta

import pytest

from conftest import make_counting_sequence, make_pce, make_stop


def test_combine_sums_counts_of_same_door(base_time):
    stop = make_stop(1, 1)
    a = make_pce(stop, make_counting_sequence(base_time, count_in=1, count_out=2))
    b = make_pce(stop, make_counting_sequence(base_time, count_in=3, count_out=4))

    a.combine(b)

    assert (a.count_in(), a.count_out()) == (4, 6)
    assert len(a.counting_sequences) == 1


def test_combine_same_door_of_different_device_fails(base_time):
    stop = make_stop(1, 1)
    a = make_pce(stop, make_counting_sequence(base_time, device_id='a'), device_id='a')
    b = make_pce(stop, make_counting_sequence(base_time, device_id='b'), device_id='b')

    with pytest.raises(ValueError):
        a.combine(b)


def test_intersects_requires_same_stop_and_overlapping_time(base_time):
    stop = make_stop(1, 1)
    a = make_pce(stop, make_counting_sequence(base_time, base_time + timedelta(seconds=30)))
    overlapping = make_pce(stop, make_counting_sequence(base_time + timedelta(seconds=10), base_time + timedelta(seconds=40)))
    later = make_pce(stop, make_counting_sequence(base_time + timedelta(minutes=5)))
    other_stop = make_pce(make_stop(2, 2), make_counting_sequence(base_time))

    assert a.intersects(overlapping)
    assert not a.intersects(later)
    assert not a.intersects(other_stop)
