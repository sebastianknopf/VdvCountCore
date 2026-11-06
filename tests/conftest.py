from datetime import datetime, timedelta, timezone

import pytest

from vcclib.dataclasses import CountingSequence, Line, PassengerCountingEvent, Stop, StopTime, Trip

BASE_TIME = datetime(2025, 1, 1, 8, 0, 0, tzinfo=timezone.utc)


def make_stop(stop_id: int, sequence: int, lat: float = 48.0, lon: float = 9.0) -> Stop:
    stop = Stop()
    stop.id = stop_id
    stop.parent_id = stop_id
    stop.sequence = sequence
    stop.latitude = lat
    stop.longitude = lon
    return stop


def make_counting_sequence(begin: datetime, end: datetime | None = None, door_id: str = '1',
                           count_in: int = 0, count_out: int = 0, device_id: str = 'dev1') -> CountingSequence:
    cs = CountingSequence()
    cs.begin_timestamp = begin
    cs.end_timestamp = end if end is not None else begin
    cs.counting_area_id = '1'
    cs.door_id = door_id
    cs.object_class = 'Adult'
    cs.count_in = count_in
    cs.count_out = count_out
    cs.device_id = device_id
    return cs


def make_pce(stop: Stop | None, *counting_sequences: CountingSequence, device_id: str = 'dev1') -> PassengerCountingEvent:
    pce = PassengerCountingEvent()
    pce.stop = stop
    pce.device_id = device_id
    pce.counting_sequences.extend(counting_sequences)
    return pce


def ts(offset_seconds: int = 0) -> int:
    """Unix timestamp relative to BASE_TIME, as delivered by the raw data."""
    return int(BASE_TIME.timestamp()) + offset_seconds


def make_row(stop_id: int | None = 1, begin: int = 0, end: int | None = None, door_id: str = '1',
             count_in: int = 1, count_out: int = 0, object_class: str = 'Adult', area_id: str = '1',
             sequence: int | None = None, after_stop_sequence: int = -1, counting_type: str = 'COMPARISON',
             lat: float = 48.0, lon: float = 9.0) -> dict:
    """One row as returned by DuckDB.get_data(); begin/end are seconds relative to BASE_TIME."""
    return {
        'stop_id': stop_id,
        'stop_parent_id': stop_id,
        'stop_international_id': f'de:stop:{stop_id}' if stop_id is not None else None,
        'stop_latitude': lat,
        'stop_longitude': lon,
        'stop_name': f'Stop {stop_id}' if stop_id is not None else None,
        'stop_sequence': sequence if sequence is not None else stop_id,
        'pce_latitude': lat,
        'pce_longitude': lon,
        'pce_after_stop_sequence': after_stop_sequence,
        'door_id': door_id,
        'counting_area_id': area_id,
        'object_class': object_class,
        'counting_type': counting_type,
        'begin_timestamp': ts(begin),
        'end_timestamp': ts(begin + 10 if end is None else end),
        'in': count_in,
        'out': count_out,
    }


def trip_details_rows(trip: Trip) -> list[dict]:
    """Rows as returned by DuckDB.get_trip_details() for the given trip."""
    rows = []
    for st in trip.stop_times:
        rows.append({
            'line_id': trip.line.id,
            'line_international_id': trip.line.international_id,
            'line_name': trip.line.name,
            'trip_id': trip.id,
            'trip_international_id': trip.international_id,
            'vehicle_id': trip.vehicle_id,
            'vehicle_num_doors': trip.vehicle_num_doors,
            'direction': trip.direction,
            'counting_type': trip.counting_type,
            'stop_id': st.stop.id,
            'stop_parent_id': st.stop.parent_id,
            'stop_international_id': st.stop.international_id,
            'stop_latitude': st.stop.latitude,
            'stop_longitude': st.stop.longitude,
            'stop_name': f'Stop {st.stop.id}',
            'stop_sequence': st.stop.sequence,
            'nom_arrival_timestamp': int(st.arrival_time.timestamp()) if st.arrival_time else 0,
            'nom_departure_timestamp': int(st.departure_time.timestamp()) if st.departure_time else 0,
        })
    return rows


class FakeDuckDB:
    """In-memory replacement for vcclib.duckdb.DuckDB."""

    def __init__(self, trip: Trip, primary: dict, secondary: dict | None = None, data: dict | None = None):
        self._trip = trip
        self._primary = primary
        self._secondary = secondary or {}
        self._data = data or {}

    def get_primary_indicators(self) -> dict:
        return dict(self._primary)

    def get_secondary_device_ids(self, operation_day, trip_id, vehicle_id, primary_device_id) -> list:
        return list(self._secondary.get((operation_day, trip_id, vehicle_id), []))

    def get_data(self, operation_day, trip_id, vehicle_id, device_id) -> list:
        return list(self._data.get((operation_day, trip_id, vehicle_id, device_id), []))

    def get_trip_details(self, operation_day, trip_id, vehicle_id) -> list:
        return trip_details_rows(self._trip)

    def get_counting_types(self, operation_day, trip_id, vehicle_id) -> list:
        counting_types = set()
        for (od, tid, vid, _), rows in self._data.items():
            if od == operation_day and tid == trip_id and vid == vehicle_id:
                for row in rows:
                    counting_types.add(row.get('counting_type', 'COMPARISON') or 'COMPARISON')

        return sorted(counting_types) if len(counting_types) > 0 else ['COMPARISON']


TRIP_KEY = (20250101, 1, 'v1')


def trip_rows(doors=('1', '2'), count_in=1, count_out=0) -> list[dict]:
    """Raw rows of one device: one PCE per nominal stop (stop 100..102), 5 minutes apart."""
    rows = []
    for i in range(3):
        for door in doors:
            rows.append(make_row(100 + i, begin=300 * i, end=300 * i + 20, door_id=door,
                                 count_in=count_in, count_out=count_out, sequence=i + 1))
    return rows


def make_ddb(trip: Trip, primary_rows: list | None = None, secondary: dict | None = None) -> 'FakeDuckDB':
    data = {TRIP_KEY + ('primary',): trip_rows() if primary_rows is None else primary_rows}
    secondary_ids = []
    for device_id, rows in (secondary or {}).items():
        data[TRIP_KEY + (device_id,)] = rows
        secondary_ids.append(device_id)

    return FakeDuckDB(trip, {TRIP_KEY: 'primary'}, {TRIP_KEY: secondary_ids}, data)


@pytest.fixture
def dirs(tmp_path):
    success, dubious = tmp_path / 'success', tmp_path / 'dubious'
    success.mkdir()
    dubious.mkdir()
    return str(success), str(dubious)


@pytest.fixture
def base_time() -> datetime:
    return BASE_TIME


@pytest.fixture
def trip() -> Trip:
    """Trip with three stops, five minutes apart each."""
    line = Line()
    line.id = 1
    line.international_id = 'de:test:1'
    line.name = '1'

    trip = Trip()
    trip.id = 1
    trip.line = line
    trip.vehicle_id = 'v1'
    trip.vehicle_num_doors = 2
    trip.direction = 1

    for i in range(3):
        st = StopTime()
        st.stop = make_stop(100 + i, i + 1)
        st.arrival_time = BASE_TIME + timedelta(minutes=5 * i)
        st.departure_time = BASE_TIME + timedelta(minutes=5 * i, seconds=30)
        trip.stop_times.append(st)

    return trip
