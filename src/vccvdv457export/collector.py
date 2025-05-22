import logging

from typing import List

from vcclib.model import PassengerCountingEvent
from vcclib.model import CountingSequence

class PassengerCountingEventCollector:

    def __init__(self, primary_data: List[tuple]) -> None:
        self._passenger_counting_events = self._extract_passenger_counting_events(primary_data)

    def add(self, secondary_data: List[tuple]) -> None:
        passenger_counting_events = self._extract_passenger_counting_events(secondary_data)

        logging.info(f"Combining {len(passenger_counting_events)} secondary PCEs with {len(self._passenger_counting_events)} existing PCEs")
        self._combine_passenger_counting_events(passenger_counting_events)
            
    def get_passenger_counting_events(self) -> List[PassengerCountingEvent]:
        return self._passenger_counting_events
    
    def _extract_passenger_counting_events(self, data: List[tuple]) -> List[PassengerCountingEvent]:
        pass

    def _combine_passenger_counting_events(self, passenger_counting_events: List[PassengerCountingEvent]) -> None:
        pass