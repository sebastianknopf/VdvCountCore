import logging

from typing import Dict
from typing import List

from vcclib.dataclasses import PassengerCountingEvent
from vcclib.duckdb import DuckDB
from vcclib.xml import dict2xml

from vccvdv457export.adapter.base import BaseAdapter
from vccvdv457export.collector import PassengerCountingEventCollector

class DefaultAdapter(BaseAdapter):

    def __init__(self) -> None:
        pass

    def process(self, ddb: DuckDB, output_directory: str) -> None:
        super().process(ddb, output_directory)

        # extract PCE from loaded data
        extracted_data: Dict[tuple, List[PassengerCountingEvent]] = self._extract(ddb)

        # transform each operation_day/trip_id combination into final data structure
        transformed_data: List[str] = list()
        for (operation_day, trip_id), passenger_counting_events in extracted_data.items():
            transformed_data.append(
                self._transform(operation_day, trip_id, passenger_counting_events)
            )

        # export data finally
        self._export(transformed_data)

        logging.info(f"Exported {len(transformed_data)} trips total")

    def _extract(self, ddb: DuckDB) -> Dict[tuple, List[PassengerCountingEvent]]:

        results: Dict[tuple, List[PassengerCountingEvent]] = dict()

        logging.info("Loading primary indicators")
        for (operation_day, trip_id), primary_device_id in ddb.get_primary_indicators().items():

            logging.info(f"Processing trip ID {trip_id} at {operation_day}, primary device is {primary_device_id}")

            # select primary data and create collector instance
            primary_data = ddb.get_data(operation_day, trip_id, primary_device_id)
            collector: PassengerCountingEventCollector = PassengerCountingEventCollector(primary_data)
            
            # select device IDs for secondary data
            for secondary_device_id in ddb.get_secondary_device_ids(operation_day, trip_id, primary_device_id):

                logging.info(f"Adding secondary data of device {secondary_device_id}")

                # select secondary data 
                secondary_data = ddb.get_data(operation_day, trip_id, secondary_device_id)
                collector.add(secondary_data)

            # call verify method to log every possible invalid dataset
            collector.verify()

            # return finally generated PCE data
            passenger_counting_events = collector.get_passenger_counting_events()

            logging.info(f"Found total {len(passenger_counting_events)} PCEs")

            results[(operation_day, trip_id)] = passenger_counting_events
        
        # finally return generated results
        return results
    
    def _transform(self, operation_day: int, trip_id: int, passenger_counting_events: List[PassengerCountingEvent]) -> str:

        result: dict = dict()

        # todo: implementation following here

        return dict2xml(result)
    
    def _export(self, transformed_data: List[str]) -> None:
        pass