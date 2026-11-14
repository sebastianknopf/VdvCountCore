import os
from datetime import timedelta

import pytest
import xmltodict

from conftest import (BASE_TIME, TRIP_KEY as KEY, FakeDuckDB, make_counting_sequence, make_ddb, make_pce,
                      make_row, trip_rows)
from vccvdv457export.adapter.s3.default import DefaultAdapter

FORCE_LIST = ('PassengerCountingEvent', 'CountingArea', 'Counting', 'Count')


def parse(xml):
    root = xmltodict.parse(xml, force_list=FORCE_LIST)['PassengerCountingServiceBGS_457-3.GetAllDataResponse']
    return root['PassengerCountingServiceJourney']


def pce_at(stop, begin: int, end: int | None = None, door_id: str = '1', count_in: int = 1):
    pce = make_pce(stop, make_counting_sequence(
        BASE_TIME + timedelta(seconds=begin),
        BASE_TIME + timedelta(seconds=begin if end is None else end),
        door_id=door_id, count_in=count_in))
    pce.latitude, pce.longitude = (stop.latitude, stop.longitude) if stop is not None else (48.0, 9.0)
    return pce


class TestExtract:

    def test_returns_pces_per_trip_key(self, trip):
        result = DefaultAdapter()._extract(make_ddb(trip))

        assert list(result.keys()) == [KEY]
        assert [p.stop.sequence for p in result[KEY]] == [1, 2, 3]

    def test_no_primary_indicators_yields_empty_result(self, trip):
        assert DefaultAdapter()._extract(FakeDuckDB(trip, {})) == {}

    def test_secondary_data_is_combined_regardless_of_time(self, trip):
        late_rows = [make_row(100, begin=3000, end=3020, door_id='3', count_in=4, sequence=1)]

        result = DefaultAdapter()._extract(make_ddb(trip, secondary={'secondary': late_rows}))[KEY]

        assert len(result) == 3
        first = next(p for p in result if p.stop.sequence == 1)
        assert sorted(cs.door_id for cs in first.counting_sequences) == ['1', '2', '3']

    def test_conflicting_door_of_secondary_device_raises(self, trip):
        with pytest.raises(ValueError):
            DefaultAdapter()._extract(make_ddb(trip, secondary={'secondary': trip_rows(doors=('1',))}))


class TestUpdateUnmatchedPces:

    def update(self, trip, pces):
        return DefaultAdapter()._update_unmatched_pces(trip, pces)

    def test_empty_list_stays_empty(self, trip):
        assert self.update(trip, []) == []

    def test_pce_is_assigned_to_next_stop_after_after_stop_sequence(self, trip):
        pce = pce_at(None, 100)
        pce.after_stop_sequence = 1

        [result] = self.update(trip, [pce])

        assert result.stop is trip.stop_times[1].stop
        assert result.after_stop_sequence == -1

    def test_pce_after_last_stop_is_dropped(self, trip):
        pce = pce_at(None, 100)
        pce.after_stop_sequence = 3

        assert self.update(trip, [pce]) == []

    def test_matched_pces_are_returned_unchanged(self, trip):
        pces = [pce_at(st.stop, 300 * i) for i, st in enumerate(trip.stop_times)]

        assert self.update(trip, pces) == pces

    def test_single_run_through_pce_is_kept(self, trip):
        run_through = pce_at(trip.stop_times[0].stop, 10, door_id='0')

        assert self.update(trip, [run_through]) == [run_through]

    def test_run_through_pce_is_dropped_when_real_pce_exists_at_same_stop(self, trip):
        stop = trip.stop_times[0].stop
        real = pce_at(stop, 10, 20, door_id='1', count_in=3)
        run_through = pce_at(stop, 5, door_id='0')

        [result] = self.update(trip, [run_through, real])

        assert result is real
        assert result.count_in() == 3

    def test_multiple_real_pces_at_same_stop_are_combined(self, trip):
        stop = trip.stop_times[0].stop
        first = pce_at(stop, 10, 20, door_id='1', count_in=3)
        second = pce_at(stop, 30, 40, door_id='2', count_in=4)

        [result] = self.update(trip, [first, second])

        assert result is first
        assert result.count_in() == 7
        assert sorted(cs.door_id for cs in result.counting_sequences) == ['1', '2']

    def test_unmatched_pce_is_merged_with_pce_of_the_next_stop(self, trip):
        existing = pce_at(trip.stop_times[1].stop, 300, 310, door_id='1', count_in=2)
        unmatched = pce_at(None, 250, 260, door_id='2', count_in=5)
        unmatched.after_stop_sequence = 1

        [result] = self.update(trip, [existing, unmatched])

        assert result.count_in() == 7

    def test_result_is_sorted_by_end_timestamp(self, trip):
        late = pce_at(trip.stop_times[0].stop, 1000)
        early = pce_at(trip.stop_times[1].stop, 10)

        assert self.update(trip, [late, early]) == [early, late]

    def test_combining_pces_of_different_devices_with_same_door_raises(self, trip):
        stop = trip.stop_times[0].stop
        first = pce_at(stop, 10, 20, door_id='1')
        second = pce_at(stop, 30, 40, door_id='1')
        second.counting_sequences[0].device_id = 'other'

        with pytest.raises(ValueError):
            self.update(trip, [first, second])

    @pytest.mark.xfail(strict=True, raises=IndexError, reason="Known bug: only run-through PCEs at the same stop lead to an IndexError")
    def test_multiple_run_through_pces_at_same_stop_can_be_handled(self, trip):
        stop = trip.stop_times[0].stop

        result = self.update(trip, [pce_at(stop, 10, door_id='0'), pce_at(stop, 20, door_id='0')])

        assert len(result) == 1


class TestTransform:

    def transform(self, trip, rows=None, secondary=None):
        adapter = DefaultAdapter()
        pces = adapter._extract(make_ddb(trip, rows, secondary))[KEY]
        key, xml, _ = adapter._transform(FakeDuckDB(trip, {}), *KEY, pces)
        assert key == KEY
        return parse(xml), adapter

    def test_journey_header(self, trip):
        journey, _ = self.transform(trip)

        header = journey['HeaderServiceJourney']
        assert header['ServiceJourneyID'] == '1'
        assert header['DataType'] == 'RawData'
        assert header['ServiceJourneyDepartureTime'] == '2025-01-01T08:00:30+00:00'
        assert header['ServiceJourneyDestinationTime'] == '2025-01-01T08:10:00+00:00'
        assert (header['Origin'], header['Destination']) == ('100', '102')
        assert header['Line']['LineRef']['Value'] == '1'
        assert header['Line']['LineName']['Value'] == '1'
        assert header['Line']['DirectionType'] == '1'

    def test_message_header_contains_vehicle(self, trip):
        journey, _ = self.transform(trip)

        assert journey['PassengerCountingMessage']['HeaderData']['VehicleID'] == 'v1'

    def test_one_event_per_nominal_stop(self, trip):
        journey, _ = self.transform(trip)

        events = journey['PassengerCountingMessage']['PassengerCountingEvent']
        assert [e['StopInformation']['StopRef']['Value'] for e in events] == ['100', '101', '102']
        assert [e['StopInformation']['StopName']['Value'] for e in events] == ['Stop 100', 'Stop 101', 'Stop 102']

    def test_counting_area_header_contains_sequence_and_timestamps(self, trip):
        journey, _ = self.transform(trip)

        events = journey['PassengerCountingMessage']['PassengerCountingEvent']
        header = events[1]['CountingArea'][0]['HeaderCounting']
        assert header['SequentialNumber'] == '2'
        assert header['TimeStampEventStart']['Value'] == '2025-01-01T08:05:00+00:00'
        assert header['TimeStampEventEnd']['Value'] == '2025-01-01T08:05:20+00:00'

    def test_counts_are_exported_per_door(self, trip):
        journey, _ = self.transform(trip, trip_rows(count_in=3, count_out=2))

        [area] = journey['PassengerCountingMessage']['PassengerCountingEvent'][0]['CountingArea']
        assert sorted(c['DoorID']['Value'] for c in area['Counting']) == ['1', '2']
        for counting in area['Counting']:
            [count] = counting['Count']
            assert (count['In']['Value'], count['Out']['Value']) == ('3', '2')

    def test_missing_stops_are_added_as_empty_events(self, trip):
        journey, _ = self.transform(trip, trip_rows()[:2])

        events = journey['PassengerCountingMessage']['PassengerCountingEvent']
        assert len(events) == 3
        count = events[1]['CountingArea'][0]['Counting'][0]['Count'][0]
        assert (count['In']['Value'], count['Out']['Value']) == ('0', '0')

    def test_run_through_door_id_is_configurable(self, trip, monkeypatch):
        monkeypatch.setenv('VCC_VDV457_EXPORT_RUN_THROUGH_DOOR_ID', '99')

        journey, _ = self.transform(trip, trip_rows()[:2])

        events = journey['PassengerCountingMessage']['PassengerCountingEvent']
        assert events[1]['CountingArea'][0]['Counting'][0]['DoorID']['Value'] == '99'

    def test_secondary_data_is_included_in_export(self, trip):
        journey, _ = self.transform(trip, secondary={'secondary': trip_rows(doors=('3',), count_in=4)})

        area = journey['PassengerCountingMessage']['PassengerCountingEvent'][0]['CountingArea'][0]
        assert sorted(c['DoorID']['Value'] for c in area['Counting']) == ['1', '2', '3']

    def test_after_stop_pces_are_reported_on_next_stop(self, trip):
        rows = trip_rows() + [make_row(stop_id=None, begin=150, end=160, door_id='1', count_in=9, after_stop_sequence=1)]

        journey, _ = self.transform(trip, rows)

        events = journey['PassengerCountingMessage']['PassengerCountingEvent']
        assert len(events) == 3
        counting = next(c for c in events[1]['CountingArea'][0]['Counting'] if c['DoorID']['Value'] == '1')
        assert counting['Count'][0]['In']['Value'] == '10'

    def test_verification_reports_are_collected(self, trip):
        _, adapter = self.transform(trip, trip_rows(doors=('1',)))

        assert [r['log_code'] for r in adapter._reports] == [903]

    def test_stop_without_departure_time_as_origin_raises(self, trip):
        class NoDepartureDDB(FakeDuckDB):
            def get_trip_details(self, *args):
                rows = super().get_trip_details(*args)
                rows[0]['nom_departure_timestamp'] = 0
                return rows

        adapter = DefaultAdapter()
        pces = adapter._extract(make_ddb(trip))[KEY]

        with pytest.raises(AttributeError):
            adapter._transform(NoDepartureDDB(trip, {}), *KEY, pces)


class TestProcess:

    def test_writes_xml_to_success_directory(self, trip, dirs):
        DefaultAdapter('archive').process(make_ddb(trip), *dirs)

        [filename] = os.listdir(dirs[0])
        assert filename.endswith('_O20250101_T1_v1.xml')
        with open(os.path.join(dirs[0], filename)) as f:
            assert len(parse(f.read())['PassengerCountingMessage']['PassengerCountingEvent']) == 3
        assert os.listdir(dirs[1]) == []

    def test_data_with_errors_goes_to_invalid_directory(self, trip, dirs):
        DefaultAdapter('archive').process(make_ddb(trip, trip_rows(doors=('1',))), *dirs)

        assert os.listdir(dirs[0]) == []
        assert len(os.listdir(dirs[1])) == 1

    def test_report_files_are_created_when_enabled(self, trip, dirs):
        DefaultAdapter('archive', reports_create=True).process(make_ddb(trip), *dirs)

        assert sorted(f.rsplit('_', 1)[-1] for f in os.listdir(dirs[0])) == ['Report.txt', 'v1.xml']

    def test_empty_database_writes_nothing(self, trip, dirs):
        DefaultAdapter().process(FakeDuckDB(trip, {}), *dirs)

        assert os.listdir(dirs[0]) == [] and os.listdir(dirs[1]) == []

    def test_primary_without_rows_is_exported_as_invalid_empty_journey(self, trip, dirs):
        adapter = DefaultAdapter('archive')

        adapter.process(make_ddb(trip, primary_rows=[]), *dirs)

        # first/last stop not counted and no door counted at all
        assert sorted(r['log_code'] for r in adapter._reports) == [801, 802, 903]
        assert os.listdir(dirs[0]) == []
        assert len(os.listdir(dirs[1])) == 1
