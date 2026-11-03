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
    trip.vehicle_num_doors = '2'
    trip.direction = 1

    for i in range(3):
        st = StopTime()
        st.stop = make_stop(100 + i, i + 1)
        st.arrival_time = BASE_TIME + timedelta(minutes=5 * i)
        st.departure_time = BASE_TIME + timedelta(minutes=5 * i, seconds=30)
        trip.stop_times.append(st)

    return trip
