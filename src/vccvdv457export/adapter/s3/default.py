import logging
import os

from datetime import datetime
from typing import Dict
from typing import List
from typing import Set
from typing import Tuple

from vcclib.common import isoformattime
from vcclib.dataclasses import PassengerCountingEvent
from vcclib.dataclasses import CountingSequence
from vcclib.duckdb import DuckDB

from vccvdv457export.adapter.base import BaseAdapter
from vccvdv457export.collector import PassengerCountingEventCollector

class DefaultAdapter(BaseAdapter):

    def __init__(self) -> None:
        pass

    def process(self, ddb: DuckDB, output_directory: str) -> None:
        super().process(ddb, output_directory)

        # extract PCE from loaded data
        logging.info("Extracting PCE data from local DDB ...")
        extracted_data: Dict[tuple, List[PassengerCountingEvent]] = self._extract(ddb)

        # transform each operation_day/trip_id combination into final data structure
        logging.info(f"Transforming data of {len(extracted_data.keys())} trips ...")

        transformed_data: Dict[tuple, str] = dict()
        for (operation_day, trip_id, vehicle_id), passenger_counting_events in extracted_data.items():
            key, value = self._transform(ddb, operation_day, trip_id, vehicle_id, passenger_counting_events)
            transformed_data[key] = value

        # export data finally
        logging.info(f"Exporting {len(transformed_data)} trips ...")
        self._export(transformed_data, output_directory)

    def _extract(self, ddb: DuckDB) -> Dict[tuple, List[PassengerCountingEvent]]:
        
        results: Dict[tuple, List[PassengerCountingEvent]] = dict()

        logging.info("Loading primary indicators")
        for (operation_day, trip_id, vehicle_id), primary_device_id in ddb.get_primary_indicators().items():

            logging.info(f"Processing trip ID {trip_id} with vehicle ID {vehicle_id} at {operation_day}, primary device is {primary_device_id}")

            # select primary data and create collector instance
            primary_data = ddb.get_data(operation_day, trip_id, vehicle_id, primary_device_id)
            collector: PassengerCountingEventCollector = PassengerCountingEventCollector(primary_data)
            
            # select device IDs for secondary data
            for secondary_device_id in ddb.get_secondary_device_ids(operation_day, trip_id, vehicle_id, primary_device_id):

                logging.info(f"Adding secondary data of device {secondary_device_id}")

                # select secondary data 
                secondary_data = ddb.get_data(operation_day, trip_id, vehicle_id, secondary_device_id)
                collector.add(secondary_data, False)

            # call verify method to log every possible invalid dataset
            collector.verify()

            # return finally generated PCE data
            passenger_counting_events = collector.get_passenger_counting_events()

            logging.info(f"Found total {len(passenger_counting_events)} PCEs")

            results[(operation_day, trip_id, vehicle_id)] = passenger_counting_events
        
        # finally return generated results
        return results

    def _transform(self, ddb: DuckDB, operation_day: int, trip_id: int, vehicle_id: str, passenger_counting_events: List[PassengerCountingEvent]) -> Tuple[tuple, str]:
        pass

    def _export(self, transformed_data: Dict[tuple, str], output_directory: str) -> None:   
        
        # write each dataset to a single file
        for k, x in transformed_data.items():

            formatted_date: str = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')

            operation_day: int = k[0]
            trip_id: int = k[1]
            vehicle_id: str = k[2]

            output_filename: str = os.path.join(
                output_directory, 
                f"{formatted_date}_O{operation_day}_T{trip_id}_{vehicle_id}.xml"
            )

            with open(output_filename, 'wb') as output_file:
                output_file.write(b'<?xml version="1.0" encoding="UTF-8" ?>\n')
                output_file.write(x)