from vccvdv452import.adapter.default import DefaultAdapter


class VvsAdapter(DefaultAdapter):
    
    def process(self, input_directory: str) -> None:
        super().process(input_directory)

    def _convert_coordinate(self, input: float|str) -> float:
        if type(input) == str:
            input = float(input)
            
        return input / 10000000.0