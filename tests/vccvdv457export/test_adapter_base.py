import csv
import os
from datetime import datetime, timezone

import pytest

from conftest import FakeDuckDB, make_counting_sequence, make_pce, make_stop, trip_details_rows
from vccvdv457export.adapter.base import BaseAdapter


class DummyAdapter(BaseAdapter):
    def process(self, ddb, output_directory, invalid_output_directory):
        pass


def codes(adapter: BaseAdapter) -> list:
    return [r['log_code'] for r in adapter._reports]


def counted_pces(trip, doors=('1', '2')):
    """One PCE per nominal stop, exactly at the nominal position, counting all given doors."""
    pces = [
        make_pce(st.stop, *[make_counting_sequence(st.departure_time, door_id=d, count_in=1) for d in doors])
        for st in trip.stop_times
    ]
    for pce in pces:
        pce.latitude, pce.longitude = pce.stop.latitude, pce.stop.longitude

    return pces


class TestLoadTripDetails:

    def test_maps_line_trip_and_stops(self, trip):
        trip.international_id = 'de:trip:1'

        loaded = DummyAdapter().load_trip_details(FakeDuckDB(trip, {}), 20250101, 1, 'v1')

        assert (loaded.id, loaded.vehicle_id, loaded.vehicle_num_doors, loaded.direction) == (1, 'v1', 2, 1)
        assert loaded.international_id == 'de:trip:1'
        assert (loaded.line.id, loaded.line.international_id, loaded.line.name) == (1, 'de:test:1', '1')
        assert [st.stop.sequence for st in loaded.stop_times] == [1, 2, 3]
        assert loaded.stop_times[0].stop.name == 'Stop 100'

    def test_converts_nominal_times_to_utc(self, trip):
        loaded = DummyAdapter().load_trip_details(FakeDuckDB(trip, {}), 20250101, 1, 'v1')

        assert loaded.stop_times[0].arrival_time == trip.stop_times[0].arrival_time
        assert loaded.stop_times[0].arrival_time.tzinfo == timezone.utc
        assert loaded.stop_times[0].departure_time == trip.stop_times[0].departure_time

    def test_zero_timestamps_become_none(self, trip):
        class ZeroTimeDDB(FakeDuckDB):
            def get_trip_details(self, *args):
                rows = trip_details_rows(self._trip)
                rows[0]['nom_arrival_timestamp'] = 0
                rows[-1]['nom_departure_timestamp'] = 0
                return rows

        loaded = DummyAdapter().load_trip_details(ZeroTimeDDB(trip, {}), 20250101, 1, 'v1')

        assert loaded.stop_times[0].arrival_time is None
        assert loaded.stop_times[0].departure_time is not None
        assert loaded.stop_times[-1].departure_time is None

    def test_unknown_trip_raises(self, trip):
        class EmptyDDB(FakeDuckDB):
            def get_trip_details(self, *args):
                return []

        with pytest.raises(IndexError):
            DummyAdapter().load_trip_details(EmptyDDB(trip, {}), 20250101, 1, 'v1')

    def test_conflicting_counting_types_raise(self, trip):
        class ConflictingCountingTypeDDB(FakeDuckDB):
            def get_counting_types(self, *args):
                return ['COMPARISON', 'PRODUCTION']

        with pytest.raises(ValueError, match='conflicting counting_type'):
            DummyAdapter().load_trip_details(ConflictingCountingTypeDDB(trip, {}), 20250101, 1, 'v1')

    def test_missing_counting_type_defaults_to_comparison(self, trip):
        class MissingCountingTypeDDB(FakeDuckDB):
            def get_counting_types(self, *args):
                return []

        loaded = DummyAdapter().load_trip_details(MissingCountingTypeDDB(trip, {}), 20250101, 1, 'v1')

        assert loaded.counting_type == 'COMPARISON'


class TestVerificationReports:

    def verify(self, trip, pces, adapter=None):
        adapter = adapter or DummyAdapter('archive')
        adapter.generate_verification_reports(20250101, 1, 'v1', pces, trip)
        return adapter

    def test_complete_data_creates_no_reports(self, trip):
        assert self.verify(trip, counted_pces(trip))._reports == []

    def test_report_entries_contain_trip_identification(self, trip):
        adapter = self.verify(trip, [])

        report = adapter._reports[0]
        assert report['archive_name'] == 'archive'
        assert (report['operation_day'], report['trip_id'], report['vehicle_id']) == (20250101, 1, 'v1')
        assert report['comment'] is None

    def test_missing_first_stop_is_warning_801(self, trip):
        adapter = self.verify(trip, counted_pces(trip)[1:])

        assert 801 in codes(adapter)
        assert next(r for r in adapter._reports if r['log_code'] == 801)['log_level'] == 'WARNING'

    def test_missing_last_stop_is_warning_802(self, trip):
        adapter = self.verify(trip, counted_pces(trip)[:-1])

        report = next(r for r in adapter._reports if r['log_code'] == 802)
        assert report['log_level'] == 'WARNING'

    def test_no_pces_at_all_reports_801_and_802(self, trip):
        adapter = self.verify(trip, [])

        assert 801 in codes(adapter) and 802 in codes(adapter)

    def test_first_pce_far_from_stop_is_error_901(self, trip):
        pces = counted_pces(trip)
        pces[0].latitude, pces[0].longitude = 48.0, 9.1  # ~7km away

        adapter = self.verify(trip, pces)

        report = next(r for r in adapter._reports if r['log_code'] == 901)
        assert report['log_level'] == 'ERROR'

    def test_last_pce_far_from_stop_is_error_902(self, trip):
        pces = counted_pces(trip)
        pces[-1].latitude, pces[-1].longitude = 48.0, 9.1

        adapter = self.verify(trip, pces)

        assert 902 in codes(adapter)
        assert 901 not in codes(adapter)

    def test_pce_within_500_meters_is_accepted(self, trip):
        pces = counted_pces(trip)
        pces[0].latitude = pces[0].stop.latitude + 0.003  # ~330m

        assert self.verify(trip, pces)._reports == []

    def test_pce_beyond_500_meters_is_rejected(self, trip):
        pces = counted_pces(trip)
        pces[0].latitude = pces[0].stop.latitude + 0.006  # ~670m

        assert 901 in codes(self.verify(trip, pces))

    def test_missing_door_is_error_903(self, trip):
        adapter = self.verify(trip, counted_pces(trip, doors=('1',)))

        report = next(r for r in adapter._reports if r['log_code'] == 903)
        assert report['log_level'] == 'ERROR'
        assert '0,1' in report['log_message'] and '0,1,2' in report['log_message']

    def test_unexpected_door_is_error_903(self, trip):
        assert 903 in codes(self.verify(trip, counted_pces(trip, doors=('1', '2', '3'))))

    def test_door_zero_is_always_tolerated(self, trip):
        pces = counted_pces(trip, doors=('0', '1', '2'))

        assert 903 not in codes(self.verify(trip, pces))

    def test_only_run_through_door_reports_missing_doors(self, trip):
        assert 903 in codes(self.verify(trip, counted_pces(trip, doors=('0',))))

    @pytest.mark.xfail(strict=True, raises=AttributeError, reason="Known bug: PCE without stop crashes the first stop lookup")
    def test_pce_without_stop_does_not_crash(self, trip):
        unmatched = make_pce(None, make_counting_sequence(trip.stop_times[0].departure_time, count_in=1))
        unmatched.after_stop_sequence = 1

        self.verify(trip, [unmatched] + counted_pces(trip))


class TestExport:

    @pytest.fixture
    def dirs(self, tmp_path):
        success, invalid = tmp_path / 'success', tmp_path / 'invalid'
        success.mkdir()
        invalid.mkdir()
        return str(success), str(invalid)

    def test_writes_one_xml_per_trip(self, dirs):
        DummyAdapter()._export({(20250101, 1, 'v1'): '<a/>', (20250101, 2, 'v1'): '<b/>'}, *dirs)

        files = sorted(os.listdir(dirs[0]))
        assert len(files) == 2
        assert files[0].endswith('_O20250101_T1_v1.xml')
        assert files[1].endswith('_O20250101_T2_v1.xml')
        assert open(os.path.join(dirs[0], files[0])).read() == '<a/>'

    def test_nothing_to_export_writes_nothing(self, dirs):
        DummyAdapter()._export({}, *dirs)

        assert os.listdir(dirs[0]) == [] and os.listdir(dirs[1]) == []

    def test_error_report_moves_output_to_invalid_directory(self, dirs):
        adapter = DummyAdapter()
        adapter._report(20250101, 1, 'v1', 903, 'ERROR', 'doors')

        adapter._export({(20250101, 1, 'v1'): '<a/>'}, *dirs)

        assert os.listdir(dirs[0]) == []
        assert len(os.listdir(dirs[1])) == 1

    def test_error_level_is_case_insensitive(self, dirs):
        adapter = DummyAdapter()
        adapter._report(20250101, 1, 'v1', 903, 'error', 'doors')

        adapter._export({(20250101, 1, 'v1'): '<a/>'}, *dirs)

        assert len(os.listdir(dirs[1])) == 1

    def test_warning_keeps_output_in_success_directory(self, dirs):
        adapter = DummyAdapter()
        adapter._report(20250101, 1, 'v1', 801, 'WARNING', 'first stop')

        adapter._export({(20250101, 1, 'v1'): '<a/>'}, *dirs)

        assert len(os.listdir(dirs[0])) == 1
        assert os.listdir(dirs[1]) == []

    def test_error_of_other_trip_does_not_affect_this_trip(self, dirs):
        adapter = DummyAdapter()
        adapter._report(20250101, 99, 'v1', 903, 'ERROR', 'doors')

        adapter._export({(20250101, 1, 'v1'): '<a/>'}, *dirs)

        assert len(os.listdir(dirs[0])) == 1

    @pytest.mark.xfail(strict=True, reason="Known bug: output directory stays 'invalid' for all following trips")
    def test_error_in_one_trip_does_not_move_following_trips(self, dirs):
        adapter = DummyAdapter()
        adapter._report(20250101, 1, 'v1', 903, 'ERROR', 'doors')

        adapter._export({(20250101, 1, 'v1'): '<a/>', (20250101, 2, 'v1'): '<b/>'}, *dirs)

        assert len(os.listdir(dirs[0])) == 1
        assert len(os.listdir(dirs[1])) == 1

    def test_no_report_file_unless_enabled(self, dirs):
        adapter = DummyAdapter('archive', reports_create=False)
        adapter._report(20250101, 1, 'v1', 801, 'WARNING', 'first stop')

        adapter._export({(20250101, 1, 'v1'): '<a/>'}, *dirs)

        assert [f for f in os.listdir(dirs[0]) if f.endswith('_Report.txt')] == []

    def test_report_file_contains_only_reports_of_this_trip(self, dirs):
        adapter = DummyAdapter('archive', reports_create=True)
        adapter._report(20250101, 1, 'v1', 801, 'WARNING', 'first; stop')
        adapter._report(20250101, 2, 'v1', 802, 'WARNING', 'other trip')

        adapter._export({(20250101, 1, 'v1'): '<a/>'}, *dirs)

        [report_file] = [f for f in os.listdir(dirs[0]) if f.endswith('_T1_v1_Report.txt')]
        with open(os.path.join(dirs[0], report_file)) as f:
            rows = list(csv.DictReader(f, delimiter=';', quotechar='"'))

        assert len(rows) == 1
        assert rows[0]['log_code'] == '801'
        assert rows[0]['log_message'] == 'first; stop'
        assert rows[0]['archive_name'] == 'archive'

    def test_report_file_without_reports_has_only_header(self, dirs):
        adapter = DummyAdapter('archive', reports_create=True)

        adapter._export({(20250101, 1, 'v1'): '<a/>'}, *dirs)

        [report_file] = [f for f in os.listdir(dirs[0]) if f.endswith('_Report.txt')]
        with open(os.path.join(dirs[0], report_file)) as f:
            assert len(f.read().strip().splitlines()) == 1

    def test_report_file_follows_xml_into_invalid_directory(self, dirs):
        adapter = DummyAdapter('archive', reports_create=True)
        adapter._report(20250101, 1, 'v1', 903, 'ERROR', 'doors')

        adapter._export({(20250101, 1, 'v1'): '<a/>'}, *dirs)

        assert sorted(f.rsplit('_', 1)[-1] for f in os.listdir(dirs[1])) == ['Report.txt', 'v1.xml']

    def test_missing_output_directory_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            DummyAdapter()._export({(20250101, 1, 'v1'): '<a/>'}, str(tmp_path / 'missing'), str(tmp_path / 'missing2'))
