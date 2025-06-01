from abc import ABC
from abc import abstractmethod

from datetime import datetime
from datetime import timezone

from vcclib.dataclasses import Trip
from vcclib.dataclasses import Line
from vcclib.dataclasses import StopTime
from vcclib.dataclasses import Stop
from vcclib.duckdb import DuckDB

class BaseAdapter(ABC):

    def __init__(self):
        self._ddb = DuckDB()

    @abstractmethod
    def process(self, ddb: DuckDB, output_directory: str) -> None:
        pass

    def load_trip_details(self, ddb: DuckDB, operation_day: int, trip_id: int, vehicle_id: str) -> Trip:
        trip_details_data: list = ddb.get_trip_details(
            operation_day,
            trip_id,
            vehicle_id
        )

        line: Line = Line()
        line.id = trip_details_data[0]['line_id']
        line.international_id = trip_details_data[0]['line_international_id']
        line.name = trip_details_data[0]['line_name']

        trip: Trip = Trip()
        trip.id = trip_details_data[0]['trip_id']
        trip.international_id = trip_details_data[0]['trip_international_id']
        trip.direction = trip_details_data[0]['direction']
        trip.line = line

        for tdd in trip_details_data:

            stop: Stop = Stop()
            stop.id = tdd['stop_id']
            stop.parent_id = tdd['stop_parent_id']
            stop.international_id = tdd['stop_international_id']
            stop.latitude = tdd['stop_latitude']
            stop.longitude = tdd['stop_longitude']
            stop.name = tdd['stop_name']
            stop.sequence = tdd['stop_sequence']

            stop_time: StopTime = StopTime()
            stop_time.arrival_time = datetime.fromtimestamp(tdd['nom_arrival_timestamp'], timezone.utc) if tdd['nom_arrival_timestamp'] != 0 else None
            stop_time.departure_time = datetime.fromtimestamp(tdd['nom_departure_timestamp'], timezone.utc) if tdd['nom_departure_timestamp'] != 0 else None
            stop_time.stop = stop

            trip.stop_times.append(stop_time)

        return trip
