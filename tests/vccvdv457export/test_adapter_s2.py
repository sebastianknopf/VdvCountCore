import os

import pytest
import xmltodict

from conftest import TRIP_KEY as KEY, FakeDuckDB, make_ddb, make_row, trip_rows
from vcclib.version import version
from vccvdv457export.adapter.s2.default import DefaultAdapter

FORCE_LIST = ('PassengerCountingEvent', 'CountingArea', 'Counting', 'Count')


def parse(xml):
    return xmltodict.parse(xml, force_list=FORCE_LIST)['PassengerCountingMessage']


class TestExtract:

    def test_returns_pces_per_trip_key(self, trip):
        result = DefaultAdapter()._extract(make_ddb(trip))

        assert list(result.keys()) == [KEY]
        assert [p.stop.sequence for p in result[KEY]] == [1, 2, 3]

    def test_no_primary_indicators_yields_empty_result(self, trip):
        assert DefaultAdapter()._extract(FakeDuckDB(trip, {})) == {}

    def test_secondary_device_data_is_combined_by_time(self, trip):
        secondary = {'secondary': trip_rows(doors=('3',), count_in=4)}

        result = DefaultAdapter()._extract(make_ddb(trip, secondary=secondary))[KEY]

        assert len(result) == 3
        assert all(sorted(cs.door_id for cs in p.counting_sequences) == ['1', '2', '3'] for p in result)
        assert sum(p.count_in() for p in result) == 3 * (2 + 4)

    def test_secondary_data_far_in_time_is_not_combined(self, trip):
        late_rows = [make_row(100, begin=3000, end=3020, door_id='3', sequence=1)]

        result = DefaultAdapter()._extract(make_ddb(trip, secondary={'secondary': late_rows}))[KEY]

        assert len(result) == 4

    def test_conflicting_door_of_secondary_device_raises(self, trip):
        with pytest.raises(ValueError):
            DefaultAdapter()._extract(make_ddb(trip, secondary={'secondary': trip_rows(doors=('1',))}))

    def test_primary_without_rows_yields_no_pces(self, trip):
        assert DefaultAdapter()._extract(make_ddb(trip, primary_rows=[]))[KEY] == []


class TestTransform:

    def transform(self, trip, rows=None):
        adapter = DefaultAdapter()
        pces = adapter._extract(make_ddb(trip, rows))[KEY]
        key, xml, _ = adapter._transform(FakeDuckDB(trip, {}), *KEY, pces)
        assert key == KEY
        return parse(xml), adapter

    def test_header_contains_vehicle_and_software_version(self, trip):
        message, _ = self.transform(trip)

        header = message['HeaderData']
        assert header['VehicleID'] == 'v1'
        assert header['APC-Device']['DeviceSpecification']['DeviceClass'] == 'APC'
        assert header['APC-Device']['SoftwareVersion']['VersionRef']['Value'] == version

    def test_one_event_per_nominal_stop(self, trip):
        message, _ = self.transform(trip)

        events = message['PassengerCountingEvent']
        assert [e['HeaderCountingEvent']['SequentialNumber'] for e in events] == ['1', '2', '3']
        assert [e['StopInformation']['StopIndex']['Value'] for e in events] == ['1', '2', '3']
        assert [e['StopInformation']['StopRef']['Value'] for e in events] == ['100', '101', '102']

    def test_missing_stops_are_added_as_empty_events(self, trip):
        message, _ = self.transform(trip, rows=trip_rows()[:2])

        events = message['PassengerCountingEvent']
        assert len(events) == 3
        empty = events[1]['CountingArea'][0]['Counting'][0]
        assert empty['DoorID']['Value'] == '0'
        assert empty['Count'][0]['In']['Value'] == '0'
        assert empty['Count'][0]['Out']['Value'] == '0'

    def test_event_contains_journey_and_line_information(self, trip):
        message, _ = self.transform(trip)

        event = message['PassengerCountingEvent'][0]
        assert event['JourneyInfo']['ServiceJourneyRef'] == '1'
        assert event['Line']['LineRef']['Value'] == '1'
        assert event['Line']['LineName']['Value'] == '1'
        assert event['Line']['DirectionType'] == '1'

    def test_timestamps_are_iso_formatted_utc(self, trip):
        message, _ = self.transform(trip)

        header = message['PassengerCountingEvent'][0]['HeaderCountingEvent']
        assert header['TimeStampEventStart']['Value'] == '2025-01-01T08:00:00+00:00'
        assert header['TimeStampEventEnd']['Value'] == '2025-01-01T08:00:20+00:00'
        assert header['TimeStamp']['Value'] == header['TimeStampEventEnd']['Value']

    def test_gnss_position_and_time(self, trip):
        message, _ = self.transform(trip)

        gnss = message['PassengerCountingEvent'][0]['GNSS']
        assert gnss['GNSS_Point_Structure']['Latitude']['Degree']['Value'] == '48.0'
        assert gnss['GNSS_Point_Structure']['Longitude']['Degree']['Value'] == '9.0'
        assert gnss['time']['Value'] == '08:00:20+00:00'
        assert gnss['date']['Value'] == '2025-01-01'

    def test_counts_are_exported_per_door(self, trip):
        rows = trip_rows(doors=('1', '2'), count_in=3, count_out=2)

        message, _ = self.transform(trip, rows)

        [area] = message['PassengerCountingEvent'][0]['CountingArea']
        assert area['AreaID'] == '1'
        assert sorted(c['DoorID']['Value'] for c in area['Counting']) == ['1', '2']
        for counting in area['Counting']:
            [count] = counting['Count']
            assert (count['ObjectClass'], count['In']['Value'], count['Out']['Value']) == ('Adult', '3', '2')
            assert counting['CountInfo']['DoorOpenTime']['Value'] == '2025-01-01T08:00:00+00:00'
            assert counting['CountInfo']['DoorClosingTime']['Value'] == '2025-01-01T08:00:20+00:00'

    def test_object_classes_are_exported_separately(self, trip):
        rows = trip_rows(doors=('1', '2'))
        rows.insert(1, make_row(100, begin=0, end=20, door_id='1', count_in=7, object_class='Child', sequence=1))

        message, _ = self.transform(trip, rows)

        counting = next(c for c in message['PassengerCountingEvent'][0]['CountingArea'][0]['Counting'] if c['DoorID']['Value'] == '1')
        assert {c['ObjectClass']: c['In']['Value'] for c in counting['Count']} == {'Adult': '1', 'Child': '7'}

    def test_run_through_door_id_is_configurable(self, trip, monkeypatch):
        monkeypatch.setenv('VCC_VDV457_EXPORT_RUN_THROUGH_DOOR_ID', '99')

        message, _ = self.transform(trip, rows=trip_rows()[:2])

        generated = message['PassengerCountingEvent'][1]['CountingArea'][0]['Counting'][0]
        assert generated['DoorID']['Value'] == '99'

    def test_real_doors_are_not_replaced_by_run_through_door_id(self, trip, monkeypatch):
        monkeypatch.setenv('VCC_VDV457_EXPORT_RUN_THROUGH_DOOR_ID', '99')

        message, _ = self.transform(trip)

        doors = {c['DoorID']['Value'] for c in message['PassengerCountingEvent'][0]['CountingArea'][0]['Counting']}
        assert doors == {'1', '2'}

    def test_verification_reports_are_collected(self, trip):
        _, adapter = self.transform(trip, rows=trip_rows(doors=('1',)))

        assert [r['log_code'] for r in adapter._reports] == [903]

    def test_no_reports_for_complete_data(self, trip):
        _, adapter = self.transform(trip)

        assert adapter._reports == []

    @pytest.mark.xfail(strict=True, raises=AttributeError, reason="Known bug: PCE without stop crashes verification in S2 adapter")
    def test_pce_without_stop_can_be_transformed(self, trip):
        rows = trip_rows() + [make_row(stop_id=None, begin=-100, end=-90, door_id='1', after_stop_sequence=1)]

        self.transform(trip, rows)


class TestProcess:

    def test_writes_xml_to_success_directory(self, trip, dirs):
        DefaultAdapter('archive').process(make_ddb(trip), *dirs)

        [filename] = os.listdir(dirs[0])
        assert filename.endswith('_O20250101_T1_v1.xml')
        with open(os.path.join(dirs[0], filename)) as f:
            assert len(parse(f.read())['PassengerCountingEvent']) == 3
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

    def test_missing_trip_details_raise(self, trip, dirs):
        class NoDetailsDDB(FakeDuckDB):
            def get_trip_details(self, *args):
                return []

        ddb = NoDetailsDDB(trip, {KEY: 'primary'}, data={KEY + ('primary',): trip_rows()})

        with pytest.raises(IndexError):
            DefaultAdapter().process(ddb, *dirs)
