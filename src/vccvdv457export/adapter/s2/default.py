import logging

from vcclib.duckdb import DuckDB

from vccvdv457export.adapter.base import BaseAdapter
from vccvdv457export.collector import PassengerCountingEventCollector

class DefaultAdapter(BaseAdapter):

    def __init__(self) -> None:
        pass

    def process(self, ddb: DuckDB, output_directory: str) -> None:
        super().process(ddb, output_directory)

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

            # transform collected PCEs into final structure
            passenger_counting_events = collector.get_passenger_counting_events()

            logging.info(f"Found total {len(passenger_counting_events)} PCEs")
