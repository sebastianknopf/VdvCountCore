import logging
from datetime import datetime, timedelta, timezone

from conftest import BASE_TIME, make_counting_sequence, make_pce, make_stop
from vccvdv457export.extender import PassengerCountingEventExtender


def at(seconds: int) -> datetime:
    return BASE_TIME + timedelta(seconds=seconds)


def fixed_pce(begin: int, end: int, stop=None):
    return make_pce(stop, make_counting_sequence(at(begin), at(end), door_id='1', count_in=1))


def run_through_pce(second: int, stop=None):
    return make_pce(stop, make_counting_sequence(at(second), at(second), door_id='0'))


class TestExtend:

    def test_adds_empty_pce_for_every_missing_stop(self, trip):
        result = PassengerCountingEventExtender(trip).extend([])

        assert [p.stop.sequence for p in result] == [1, 2, 3]
        assert all(p.count_in() == 0 and p.count_out() == 0 for p in result)

    def test_generated_pce_has_run_through_defaults(self, trip):
        [first, *_] = PassengerCountingEventExtender(trip).extend([])

        [cs] = first.counting_sequences
        assert (cs.door_id, cs.counting_area_id, cs.object_class) == ('0', '1', 'Adult')
        assert first.is_run_through()
        assert (first.latitude, first.longitude) == (first.stop.latitude, first.stop.longitude)

    def test_generated_pce_uses_departure_time(self, trip):
        [first, *_] = PassengerCountingEventExtender(trip).extend([])

        assert first.begin_timestamp() == trip.stop_times[0].departure_time
        assert first.end_timestamp() == trip.stop_times[0].departure_time

    def test_generated_pce_falls_back_to_arrival_time(self, trip):
        trip.stop_times[0].departure_time = None

        [first, *_] = PassengerCountingEventExtender(trip).extend([])

        assert first.end_timestamp() == trip.stop_times[0].arrival_time

    def test_keeps_existing_pce_and_only_fills_gaps(self, trip):
        existing = make_pce(trip.stop_times[1].stop, make_counting_sequence(at(300), at(310), count_in=4, count_out=2))

        result = PassengerCountingEventExtender(trip).extend([existing])

        assert len(result) == 3
        assert existing in result
        assert sum(p.count_in() for p in result) == 4
        assert sum(p.count_out() for p in result) == 2

    def test_complete_pce_list_is_not_extended(self, trip):
        existing = [
            make_pce(st.stop, make_counting_sequence(at(300 * i), at(300 * i + 10), count_in=1))
            for i, st in enumerate(trip.stop_times)
        ]

        result = PassengerCountingEventExtender(trip).extend(existing)

        assert len(result) == 3
        assert all(p in existing for p in result)

    def test_same_stop_id_with_other_sequence_is_still_missing(self, trip):
        # a looped trip may visit the same stop twice, only the sequence tells them apart
        looped_stop = make_stop(trip.stop_times[0].stop.id, 99)
        existing = make_pce(looped_stop, make_counting_sequence(at(0), at(10)))

        result = PassengerCountingEventExtender(trip).extend([existing])

        assert len(result) == 4

    def test_does_not_modify_input_list(self, trip):
        existing: list = []

        PassengerCountingEventExtender(trip).extend(existing)

        assert existing == []

    def test_result_is_ordered_by_time(self, trip):
        result = PassengerCountingEventExtender(trip).extend([])

        timestamps = [p.end_timestamp() for p in result]
        assert timestamps == sorted(timestamps)

    def test_pce_without_stop_is_kept_and_sorted_by_after_stop_sequence(self, trip):
        unmatched = make_pce(None, make_counting_sequence(at(100), at(110), count_in=1))
        unmatched.after_stop_sequence = 1

        result = PassengerCountingEventExtender(trip).extend([unmatched])

        assert unmatched in result
        assert len(result) == 4

    def test_trip_without_stop_times_returns_existing_pces(self, trip):
        trip.stop_times = []
        existing = make_pce(make_stop(1, 1), make_counting_sequence(at(0), at(10)))

        assert PassengerCountingEventExtender(trip).extend([existing]) == [existing]

    def test_trip_without_stop_times_and_no_pces_returns_empty_list(self, trip):
        trip.stop_times = []

        assert PassengerCountingEventExtender(trip).extend([]) == []


class TestTemporalSequence:

    def setup_method(self):
        self.extender = PassengerCountingEventExtender(None)

    def test_ordered_pces_are_unchanged(self):
        pces = [fixed_pce(0, 10), fixed_pce(100, 110)]

        result = self.extender._ensure_temporal_sequence(pces)

        assert (result[1].begin_timestamp(), result[1].end_timestamp()) == (at(100), at(110))
        assert (result[0].begin_timestamp(), result[0].end_timestamp()) == (at(0), at(10))

    def test_does_not_modify_the_input_list_order(self):
        pces = [fixed_pce(0, 10), fixed_pce(100, 110)]

        result = self.extender._ensure_temporal_sequence(pces)

        assert result is not pces

    def test_overlapping_run_through_pce_is_shifted_behind_previous(self):
        previous = fixed_pce(0, 600)
        current = run_through_pce(300)

        self.extender._ensure_temporal_sequence([previous, current])

        # delta of 5 minutes plus the minimum delta of 10 seconds
        assert abs(current.begin_timestamp() - at(610)) < timedelta(milliseconds=1)
        assert current.end_timestamp() == current.begin_timestamp()
        assert (previous.begin_timestamp(), previous.end_timestamp()) == (at(0), at(600))

    def test_fixed_pce_stays_when_previous_run_through_pce_is_shifted_back(self):
        previous = run_through_pce(300)
        current = fixed_pce(100, 400)

        # current.begin < previous.end, current is fixed -> previous is moved before it
        self.extender._ensure_temporal_sequence([previous, current])

        assert previous.begin_timestamp() < at(100)
        assert (current.begin_timestamp(), current.end_timestamp()) == (at(100), at(400))

    def test_two_fixed_pces_are_never_shifted(self):
        previous = fixed_pce(0, 600)
        current = fixed_pce(300, 900)

        self.extender._ensure_temporal_sequence([previous, current])

        assert (previous.begin_timestamp(), previous.end_timestamp()) == (at(0), at(600))
        assert (current.begin_timestamp(), current.end_timestamp()) == (at(300), at(900))

    def test_shift_is_at_least_the_minimum_delta(self):
        previous = fixed_pce(0, 100)
        current = run_through_pce(100)
        previous.counting_sequences[0].end_timestamp = at(100)
        current.counting_sequences[0].begin_timestamp = at(99)
        current.counting_sequences[0].end_timestamp = at(99)

        self.extender._ensure_temporal_sequence([previous, current])

        assert current.begin_timestamp() >= at(100)

    def test_shift_above_maximum_is_not_applied_and_logged(self, caplog):
        previous = fixed_pce(0, 3600)
        current = run_through_pce(0)

        with caplog.at_level(logging.WARNING):
            self.extender._ensure_temporal_sequence([previous, current])

        assert current.begin_timestamp() == at(0)
        assert any('maximum is' in r.message for r in caplog.records)

    def test_shift_exactly_at_maximum_is_applied(self):
        previous = fixed_pce(0, 1800)
        current = run_through_pce(0)

        self.extender._ensure_temporal_sequence([previous, current])

        assert current.begin_timestamp() > at(1800)

    def test_empty_and_single_lists_are_returned_as_they_are(self):
        assert self.extender._ensure_temporal_sequence([]) == []

        single = [fixed_pce(0, 10)]
        assert self.extender._ensure_temporal_sequence(single) == single

    def test_chain_of_run_through_pces_ends_up_strictly_ordered(self):
        pces = [fixed_pce(0, 600), run_through_pce(100), run_through_pce(100)]

        result = self.extender._ensure_temporal_sequence(pces)

        begins = [p.begin_timestamp() for p in result[1:]]
        assert begins == sorted(begins)
        assert begins[0] < begins[1]


class TestHelpers:

    def setup_method(self):
        self.extender = PassengerCountingEventExtender(None)

    def test_absolute_delta_is_symmetric_and_in_minutes(self):
        a, b = at(0), at(90)

        assert self.extender._get_absolute_delta_minutes(a, b) == 1.5
        assert self.extender._get_absolute_delta_minutes(b, a) == 1.5

    def test_pce_with_real_door_is_fixed(self):
        assert self.extender._is_fixed_pce(fixed_pce(0, 10))

    def test_run_through_pce_is_not_fixed(self):
        assert not self.extender._is_fixed_pce(run_through_pce(0))

    def test_pce_without_counting_sequences_is_not_fixed(self):
        assert not self.extender._is_fixed_pce(make_pce(None))

    def test_shift_moves_begin_and_end_of_first_counting_sequence(self):
        pce = run_through_pce(100)

        self.extender._shift_pce(pce, timedelta(seconds=30))

        cs = pce.counting_sequences[0]
        assert (cs.begin_timestamp, cs.end_timestamp) == (at(130), at(130))

    def test_negative_shift_moves_backwards(self):
        pce = run_through_pce(100)

        self.extender._shift_pce(pce, timedelta(seconds=-30))

        assert pce.begin_timestamp() == at(70)

    def test_shift_without_counting_sequences_raises(self):
        try:
            self.extender._shift_pce(make_pce(None), timedelta(seconds=1))
        except IndexError:
            return

        raise AssertionError('expected IndexError')
