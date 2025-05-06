from vcclib.duckdb import DuckDB

from vccvdv457export.adapter.base import BaseAdapter

class DefaultAdapter(BaseAdapter):

    def __init__(self) -> None:
        pass

    def process(self, ddb: DuckDB, output_directory: str) -> None:
        super().process(ddb, output_directory)