import csv
import os

from abc import ABC
from abc import abstractmethod
from typing import Dict

from datetime import datetime
from datetime import timezone

from vcclib.dataclasses import PassengerCountingEvent
from vcclib.dataclasses import Trip
from vcclib.dataclasses import Line
from vcclib.dataclasses import StopTime
from vcclib.dataclasses import Stop
from vcclib.duckdb import DuckDB
from vcclib.geo import haversine_distance

class BaseAdapter(ABC):

    def __init__(self, reports_archive_name:str = None, reports_create: bool = False):
        self._reports:list = list()
        self._reports_archive_name: str = reports_archive_name
        self._reports_create: bool = reports_create

    @abstractmethod
    def process(self, ddb: DuckDB, output_directory: str, dubious_output_directory:str) -> None:
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
        trip.vehicle_id = trip_details_data[0]['vehicle_id']
        trip.vehicle_num_doors = trip_details_data[0]['vehicle_num_doors']
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

    def generate_verification_reports(self, operation_day: int, trip_id: int, vehicle_id: str, passenger_counting_events: list[PassengerCountingEvent], trip: Trip) -> None:
        
        # check whether first and last stop have been counted and create an warning if not
        # check if first and last stop PCE's position matches nominal stop positions
        highest_stop_index: int = trip.stop_times[-1].stop.sequence

        first_stop_pce: PassengerCountingEvent|None = next((pce for pce in passenger_counting_events if pce.stop.sequence == 1), None)
        if first_stop_pce is None:
            self._report(
                operation_day,
                trip_id,
                vehicle_id,
                801,
                'WARNING',
                'First stop has not been counted!'
            )
        else:
            distance_in_meters: float = haversine_distance(
                (first_stop_pce.stop.latitude, first_stop_pce.stop.longitude),
                (first_stop_pce.latitude, first_stop_pce.longitude)
            )

            if distance_in_meters > 500:
                self._report(
                    operation_day,
                    trip_id,
                    vehicle_id,
                    901,
                    'ERROR',
                    'First PCE position does not match the nominal stop position!'
                )

        last_stop_pce: PassengerCountingEvent|None = next((pce for pce in passenger_counting_events if pce.stop.sequence == highest_stop_index), None)
        if last_stop_pce is None:
            self._report(
                operation_day,
                trip_id,
                vehicle_id,
                802,
                'WARNING',
                'Last stop has not been counted!'
            )
        else:
            distance_in_meters: float = haversine_distance(
                (last_stop_pce.stop.latitude, last_stop_pce.stop.longitude),
                (last_stop_pce.latitude, last_stop_pce.longitude)
            )

            if distance_in_meters > 500:
                self._report(
                    operation_day,
                    trip_id,
                    vehicle_id,
                    902,
                    'ERROR',
                    'Last PCE position does not match the nominal stop position!'
                )

        # check whether each door ID has been counted at least one time in the data
        expected_door_ids: list[str] = sorted([str(i) for i in range(1, trip.vehicle_num_doors + 1)])
        counted_door_ids: list[str] = sorted(list({cs.door_id for pce in passenger_counting_events for cs in pce.counting_sequences}))

        if not expected_door_ids == counted_door_ids:
            self._report(
                operation_day,
                trip_id,
                vehicle_id,
                903,
                'ERROR',
                f"Counted door IDs ({','.join(counted_door_ids)}) does not match the expected door IDs ({','.join(expected_door_ids)})"
            )

    
    def _report(self, operation_day: int, trip_id: int, vehicle_id: str, log_code: str, log_level: str, log_message: str ) -> None:
        self._reports.append({
            'archive_name': self._reports_archive_name,
            'operation_day': operation_day,
            'trip_id': trip_id,
            'vehicle_id': vehicle_id,
            'log_code': log_code,
            'log_level': log_level,
            'log_message': log_message,
            'comment': None
        })
    
    def _export(self, transformed_data: Dict[tuple, str], output_directory: str, dubious_output_directory: str) -> None:   
        
        # write each dataset to a single file
        for k, x in transformed_data.items():

            formatted_date: str = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')

            operation_day: int = k[0]
            trip_id: int = k[1]
            vehicle_id: str = k[2]

            # extract reports for this unique combination
            matching_reports: list = [r for r in self._reports if r['trip_id'] == trip_id and r['operation_day'] == operation_day and r['vehicle_id'] == vehicle_id]

            # map to dubious output file if we have any logs with level ERROR
            if any([True for r in matching_reports if r['log_level'].lower() == 'error']):
                output_directory = dubious_output_directory

            # generate XML output file
            output_filename: str = os.path.join(
                output_directory, 
                f"{formatted_date}_O{operation_day}_T{trip_id}_{vehicle_id}.xml"
            )

            with open(output_filename, 'w') as output_file:
                output_file.write(x)

            # generate report output file
            if self._reports_create:
                report_filename: str = os.path.join(
                    output_directory, 
                    f"{formatted_date}_O{operation_day}_T{trip_id}_{vehicle_id}_Report.txt"
                )

                with open(report_filename, 'w') as report_file:
                    csv_writer = csv.DictWriter(
                        report_file, 
                        delimiter=';', 
                        quotechar='"', 
                        fieldnames=[
                            'archive_name', 
                            'operation_day', 
                            'trip_id', 
                            'vehicle_id',
                            'log_code',
                            'log_level', 
                            'log_message', 
                            'comment'
                        ])
                    
                    reports: list = [r for r in self._reports if 
                        r['operation_day'] == operation_day
                        and r['trip_id'] == trip_id 
                        and r['vehicle_id'] == vehicle_id
                    ]

                    csv_writer.writeheader()
                    csv_writer.writerows(reports)