from abc import ABC
from abc import abstractmethod

from vcclib.duckdb import DuckDB

class BaseAdapter(ABC):

    def __init__(self):
        self._ddb = DuckDB()

    @abstractmethod
    def process(self, ddb: DuckDB, output_directory: str) -> None:
        pass