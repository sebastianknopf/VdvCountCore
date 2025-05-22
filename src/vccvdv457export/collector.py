import logging

from typing import List

from vcclib.dataclasses import Stop
from vcclib.dataclasses import CountingSequence
from vcclib.dataclasses import PassengerCountingEvent

class PassengerCountingEventCollector:

    def __init__(self, primary_data: List[tuple]) -> None:
        passenger_counting_events = self._extract_passenger_counting_events(primary_data)

        logging.info(f"Initializing {self.__class__.__name__} with {len(passenger_counting_events)} PCEs")
        self._passenger_counting_events = passenger_counting_events

    def add(self, secondary_data: List[tuple]) -> None:
        passenger_counting_events = self._extract_passenger_counting_events(secondary_data)

        logging.info(f"Combining {len(passenger_counting_events)} secondary PCEs with {len(self._passenger_counting_events)} existing PCEs")
        self._combine_passenger_counting_events(passenger_counting_events)
            
    def get_passenger_counting_events(self) -> List[PassengerCountingEvent]:
        return self._passenger_counting_events
    
    def _extract_passenger_counting_events(self, data: List[tuple]) -> List[PassengerCountingEvent]:
        results: List[PassengerCountingEvent] = list()

        pce: PassengerCountingEvent|None = None
        for row in data:
            if row['stop_id'] is not None and pce is not None and pce.stop.id == row['stop_id']:
                # generate CountingSequence and add it to existing PCE
                cs: CountingSequence = self._extract_counting_sequence(row)
                pce.counting_sequences.append(cs)
            elif row['begin_timestamp'] is not None and pce is not None and pce.begin_timestamp() == row['begin_timestamp']:
                # generate CountingSequence and add it to existing PCE
                cs: CountingSequence = self._extract_counting_sequence(row)
                pce.counting_sequences.append(cs)
            else:
                # store current PCE instance
                if pce is not None:
                    results.append(pce)

                # generate new PCE instance
                pce = PassengerCountingEvent()
                pce.latitude = row['pce_latitude']
                pce.longitude = row['pce_longitude']

                # generate first CountingSequence
                cs: CountingSequence = self._extract_counting_sequence(row)
                pce.counting_sequences.append(cs)

                # generate stop information
                if row['stop_id'] is not None:
                    stop: Stop = self._extract_stop(row)
                    pce.stop = stop
                else:
                    pce.after_stop_sequence = row['after_stop_sequence']

        # add final PCE to results
        if pce is not None:
            results.append(pce)

        return results

    def _extract_counting_sequence(self, row: dict) -> CountingSequence:
        cs: CountingSequence = CountingSequence()
        cs.door_id = row['door_id']
        cs.counting_area_id = row['counting_area_id']
        cs.object_class = row['object_class']
        cs.begin_timestamp = None
        cs.end_timestamp = None
        cs.count_in = row['in']
        cs.count_out = row['out']

        return cs
    
    def _extract_stop(self, row: dict) -> Stop:
        stop: Stop = Stop()
        stop.id = row['stop_id']
        stop.international_id = row['stop_international_id']
        stop.latitude = row['stop_latitude']
        stop.longitude = row['stop_longitude']
        stop.name = row['stop_name']
        stop.sequence = row['stop_sequence']

        return stop

    def _combine_passenger_counting_events(self, passenger_counting_events: List[PassengerCountingEvent]) -> None:
        pass