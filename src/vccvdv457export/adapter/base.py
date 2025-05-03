from abc import ABC
from abc import abstractmethod


class BaseAdapter(ABC):

    @abstractmethod
    def process(self, input_directory: str) -> None:
        pass