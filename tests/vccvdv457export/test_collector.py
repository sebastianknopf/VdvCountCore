import logging
from datetime import timezone

import pytest

from conftest import make_row, ts
from vccvdv457export.collector import PassengerCountingEventCollector


def pces(collector):
    return collector.get_passenger_counting_events()


class TestExtraction:

    def test_empty_primary_data_yields_no_events(self):
        assert pces(PassengerCountingEventCollector([], 'dev1')) == []

    def test_single_row_maps_all_fields(self):
        row = make_row(stop_id=7, begin=10, end=20, door_id='2', count_in=3, count_out=4, lat=48.5, lon=9.5)

        [pce] = pces(PassengerCountingEventCollector([row], 'dev1'))

        assert (pce.stop.id, pce.stop.parent_id, pce.stop.sequence) == (7, 7, 7)
        assert pce.stop.international_id == 'de:stop:7'
        assert pce.stop.name == 'Stop 7'
        assert (pce.latitude, pce.longitude) == (48.5, 9.5)
        assert pce.device_id == 'dev1'

        [cs] = pce.counting_sequences
        assert (cs.door_id, cs.counting_area_id, cs.object_class) == ('2', '1', 'Adult')
        assert (cs.count_in, cs.count_out) == (3, 4)
        assert cs.device_id == 'dev1'

    def test_timestamps_are_converted_to_utc(self):
        [pce] = pces(PassengerCountingEventCollector([make_row(begin=10, end=20)], 'dev1'))

        cs = pce.counting_sequences[0]
        assert cs.begin_timestamp.tzinfo == timezone.utc
        assert int(cs.begin_timestamp.timestamp()) == ts(10)
        assert int(cs.end_timestamp.timestamp()) == ts(20)

    def test_rows_of_same_stop_are_grouped_into_one_pce(self):
        rows = [make_row(1, door_id='1'), make_row(1, door_id='2')]

        [pce] = pces(PassengerCountingEventCollector(rows, 'dev1'))

        assert [cs.door_id for cs in pce.counting_sequences] == ['1', '2']

    def test_rows_of_different_stops_become_separate_pces(self):
        rows = [make_row(1, begin=0), make_row(2, begin=100)]

        result = pces(PassengerCountingEventCollector(rows, 'dev1'))

        assert [p.stop.id for p in result] == [1, 2]

    def test_rows_without_stop_use_after_stop_sequence(self):
        row = make_row(stop_id=None, begin=50, after_stop_sequence=3)

        [pce] = pces(PassengerCountingEventCollector([row], 'dev1'))

        assert pce.stop is None
        assert pce.after_stop_sequence == 3

    def test_rows_without_stop_and_same_begin_are_grouped(self):
        rows = [
            make_row(stop_id=None, begin=50, door_id='1', after_stop_sequence=3),
            make_row(stop_id=None, begin=50, door_id='2', after_stop_sequence=3),
        ]

        [pce] = pces(PassengerCountingEventCollector(rows, 'dev1'))

        assert len(pce.counting_sequences) == 2

    def test_rows_without_stop_and_different_begin_are_separate(self):
        rows = [
            make_row(stop_id=None, begin=50, after_stop_sequence=3),
            make_row(stop_id=None, begin=90, after_stop_sequence=3),
        ]

        assert len(pces(PassengerCountingEventCollector(rows, 'dev1'))) == 2

    def test_result_is_sorted_by_end_timestamp(self):
        rows = [make_row(1, begin=500), make_row(2, begin=100)]

        result = pces(PassengerCountingEventCollector(rows, 'dev1'))

        assert [p.stop.id for p in result] == [2, 1]

    def test_missing_column_raises_key_error(self):
        row = make_row()
        del row['door_id']

        with pytest.raises(KeyError):
            PassengerCountingEventCollector([row], 'dev1')

    def test_missing_timestamp_raises_type_error(self):
        row = make_row()
        row['begin_timestamp'] = None

        with pytest.raises(TypeError):
            PassengerCountingEventCollector([row], 'dev1')


class TestCombiningSecondaryData:

    def test_secondary_data_of_same_stop_and_time_is_combined(self):
        collector = PassengerCountingEventCollector(
            [make_row(1, begin=0, door_id='1', count_in=2), make_row(2, begin=300)], 'primary')

        collector.add([make_row(1, begin=2, door_id='2', count_in=5)], 'secondary')

        first = pces(collector)[0]
        assert first.stop.id == 1
        assert sorted(cs.door_id for cs in first.counting_sequences) == ['1', '2']
        assert first.count_in() == 7

    def test_counts_of_same_door_are_summed(self):
        collector = PassengerCountingEventCollector(
            [make_row(1, begin=0, door_id='0', count_in=2, count_out=1), make_row(2, begin=300)], 'primary')

        collector.add([make_row(1, begin=2, door_id='0', count_in=3, count_out=4)], 'secondary')

        first = pces(collector)[0]
        assert (first.count_in(), first.count_out()) == (5, 5)
        assert len(first.counting_sequences) == 1

    def test_door_zero_is_dropped_when_real_door_is_present(self):
        collector = PassengerCountingEventCollector(
            [make_row(1, begin=0, door_id='0', count_in=0), make_row(2, begin=300)], 'primary')

        collector.add([make_row(1, begin=2, door_id='1', count_in=4)], 'secondary')

        first = pces(collector)[0]
        assert [cs.door_id for cs in first.counting_sequences] == ['1']

    def test_secondary_pce_at_other_stop_is_kept_separately(self):
        collector = PassengerCountingEventCollector(
            [make_row(1, begin=0), make_row(2, begin=300)], 'primary')

        collector.add([make_row(3, begin=600)], 'secondary')

        assert [p.stop.id for p in pces(collector)] == [1, 2, 3]

    def test_same_stop_but_distant_in_time_is_not_combined(self):
        collector = PassengerCountingEventCollector(
            [make_row(1, begin=0, end=10), make_row(2, begin=300)], 'primary')

        collector.add([make_row(1, begin=1000, end=1010, door_id='2')], 'secondary')

        result = pces(collector)
        assert [p.stop.id for p in result] == [1, 2, 1]

    def test_consider_time_false_combines_distant_pces_of_same_stop(self):
        collector = PassengerCountingEventCollector(
            [make_row(1, begin=0, end=10), make_row(2, begin=300)], 'primary')

        collector.add([make_row(1, begin=1000, end=1010, door_id='2')], 'secondary', consider_time=False)

        result = pces(collector)
        assert len(result) == 2
        merged = next(p for p in result if p.stop.id == 1)
        assert sorted(cs.door_id for cs in merged.counting_sequences) == ['1', '2']

    def test_pce_without_stop_is_combined_via_after_stop_sequence(self):
        collector = PassengerCountingEventCollector(
            [make_row(stop_id=None, begin=0, after_stop_sequence=2, door_id='1', count_in=1), make_row(5, begin=300)], 'primary')

        collector.add([make_row(stop_id=None, begin=2, after_stop_sequence=2, door_id='2', count_in=2)], 'secondary')

        assert pces(collector)[0].count_in() == 3

    def test_pce_without_stop_with_other_after_stop_sequence_is_not_combined(self):
        collector = PassengerCountingEventCollector(
            [make_row(stop_id=None, begin=0, after_stop_sequence=2), make_row(5, begin=300)], 'primary')

        collector.add([make_row(stop_id=None, begin=2, after_stop_sequence=4, door_id='2')], 'secondary')

        assert len(pces(collector)) == 3

    def test_missing_position_of_primary_is_taken_from_secondary(self):
        collector = PassengerCountingEventCollector(
            [make_row(1, begin=0, lat=0.0, lon=0.0), make_row(2, begin=300)], 'primary')

        collector.add([make_row(1, begin=2, door_id='2', lat=48.1, lon=9.1)], 'secondary')

        first = pces(collector)[0]
        assert (first.latitude, first.longitude) == (48.1, 9.1)

    def test_same_door_of_different_devices_raises(self):
        collector = PassengerCountingEventCollector(
            [make_row(1, begin=0, door_id='1'), make_row(2, begin=300)], 'primary')

        with pytest.raises(ValueError, match='already exists'):
            collector.add([make_row(1, begin=2, door_id='1')], 'secondary')

    def test_adding_nothing_keeps_primary_pces(self):
        collector = PassengerCountingEventCollector(
            [make_row(1, begin=0), make_row(2, begin=300)], 'primary')

        collector.add([], 'secondary')

        assert [p.stop.id for p in pces(collector)] == [1, 2]

    def test_multiple_secondary_devices_are_all_merged(self):
        collector = PassengerCountingEventCollector(
            [make_row(1, begin=0, door_id='1', count_in=1), make_row(2, begin=300)], 'primary')

        collector.add([make_row(1, begin=1, door_id='2', count_in=2)], 'secondary1')
        collector.add([make_row(1, begin=2, door_id='3', count_in=3)], 'secondary2')

        first = pces(collector)[0]
        assert sorted(cs.door_id for cs in first.counting_sequences) == ['1', '2', '3']
        assert first.count_in() == 6

    @pytest.mark.xfail(strict=True, reason="Known bug: a single remaining PCE is dropped when combining (loop starts at index 1)")
    def test_single_primary_pce_survives_combining_with_secondary(self):
        collector = PassengerCountingEventCollector([make_row(1, begin=0, door_id='1', count_in=2)], 'primary')

        collector.add([make_row(1, begin=2, door_id='2', count_in=5)], 'secondary')

        [pce] = pces(collector)
        assert pce.count_in() == 7

    @pytest.mark.xfail(strict=True, reason="Known bug: a single remaining PCE is dropped when combining (loop starts at index 1)")
    def test_single_primary_pce_survives_empty_secondary_data(self):
        collector = PassengerCountingEventCollector([make_row(1, begin=0)], 'primary')

        collector.add([], 'secondary')

        assert len(pces(collector)) == 1


class TestVerify:

    def test_overlapping_pces_are_logged(self, caplog):
        collector = PassengerCountingEventCollector(
            [make_row(1, begin=0, end=100), make_row(2, begin=50, end=150)], 'dev1')

        with caplog.at_level(logging.WARNING):
            collector.verify()

        assert any('overlaps' in r.message for r in caplog.records)

    def test_non_overlapping_pces_log_no_warning(self, caplog):
        collector = PassengerCountingEventCollector(
            [make_row(1, begin=0, end=10), make_row(2, begin=100, end=110)], 'dev1')

        with caplog.at_level(logging.WARNING):
            collector.verify()

        assert not caplog.records

    def test_verify_with_no_data_does_not_fail(self):
        PassengerCountingEventCollector([], 'dev1').verify()
