from vccmdimport.adapter.csv import CsvAdapter

class DefaultAdapter(CsvAdapter):

    def __init__(self) -> None:
        pass

    def process(self, input_directory: str) -> None:
        super().process(input_directory)