from abc import ABC
from abc import abstractmethod

from vcclib.duckdb import DuckDB

class BaseAdapter(ABC):

    def __init__(self):
        self._ddb = DuckDB()

    @abstractmethod
    def process(self, input_directory: str, output_directory: str) -> None:
        self.load_ddb(input_directory)

    def load_ddb(self, input_directory: str) -> None:
        pass