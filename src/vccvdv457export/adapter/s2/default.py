import logging

from vcclib.duckdb import DuckDB

from vccvdv457export.adapter.base import BaseAdapter

class DefaultAdapter(BaseAdapter):

    def __init__(self) -> None:
        pass

    def process(self, ddb: DuckDB, output_directory: str) -> None:
        super().process(ddb, output_directory)

        for (operation_day, trip_id), device_id in ddb.get_primary_indicators().items():

            primary_data = ddb.get_primary_data(operation_day, trip_id, device_id)

            logging.info(primary_data)

            secondary_data = ddb.get_secondary_data(operation_day, trip_id, device_id)

            logging.info(secondary_data)
