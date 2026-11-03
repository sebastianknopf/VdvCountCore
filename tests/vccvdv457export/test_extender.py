from datetime import timedelta

from conftest import make_counting_sequence, make_pce
from vccvdv457export.extender import PassengerCountingEventExtender


def test_adds_empty_pce_for_every_missing_stop(trip):
    result = PassengerCountingEventExtender(trip).extend([])

    assert len(result) == 3
    assert [p.stop.sequence for p in result] == [1, 2, 3]
    assert all(p.count_in() == 0 and p.count_out() == 0 for p in result)


def test_keeps_existing_pce_and_only_fills_gaps(trip, base_time):
    stop = trip.stop_times[1].stop
    existing = make_pce(stop, make_counting_sequence(base_time + timedelta(minutes=5), count_in=4, count_out=2))

    result = PassengerCountingEventExtender(trip).extend([existing])

    assert len(result) == 3
    assert existing in result
    assert sum(p.count_in() for p in result) == 4
    assert sum(p.count_out() for p in result) == 2


def test_result_is_ordered_by_time(trip):
    result = PassengerCountingEventExtender(trip).extend([])

    timestamps = [p.end_timestamp() for p in result]
    assert timestamps == sorted(timestamps)
