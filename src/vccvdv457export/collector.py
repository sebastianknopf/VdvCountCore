import logging

from datetime import datetime
from datetime import timezone
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
            
    def verify(self) -> None:
        
        # log all PCEs found with their basic data
        logging.info("Found following PCEs ...")
        for i, pce in enumerate(self._passenger_counting_events):
            logging.info(f"{i + 1}. {str(pce)}")

        # following checks are performed during verification
        # 1. overlapping time

        for p in range(1, len(self._passenger_counting_events)):
            this_pce = self._passenger_counting_events[p]
            last_pce = self._passenger_counting_events[p - 1]

            if last_pce.begin_timestamp() <= this_pce.begin_timestamp() <= last_pce.end_timestamp():
                logging.warning(f"{p + 1}. PCE overlaps {p}. PCE in timestamp and remains to different stops")

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
            elif row['begin_timestamp'] is not None and pce is not None and int(pce.begin_timestamp().timestamp()) == row['begin_timestamp']:
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
        cs.begin_timestamp = datetime.fromtimestamp(row['begin_timestamp'], timezone.utc)
        cs.end_timestamp = datetime.fromtimestamp(row['end_timestamp'], timezone.utc)
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
        # combine secondary PCE with existing PCE
        for secondary_pce in passenger_counting_events:
            combined: bool = False
            for existing_pce in self._passenger_counting_events:
                if existing_pce.intersects(secondary_pce):
                    existing_pce.combine(secondary_pce)

                    # existing PCE found, no need to run through all other PCEs
                    logging.info(f"Combined secondary PCE {str(secondary_pce)} with existing primary PCE")

                    combined = True
                    break

            # there was no PCE found which could be combined with that
            # add it to the internal PCEs list as it is
            if not combined:
                logging.info(f"Failed to combine secondary PCE {str(secondary_pce)} with existing primary PCE")

                self._passenger_counting_events.append(secondary_pce)

        # check whether we have intersecting PCEs at all now, then combine them too
        combined_passenger_counting_events: List[PassengerCountingEvent] = list()

        # check all other PCEs available and combine them if neccessary
        for p in range(1, len(self._passenger_counting_events)):
            this_pce = self._passenger_counting_events[p]
            last_pce = self._passenger_counting_events[p - 1]

            if last_pce.intersects(this_pce):
                last_pce.combine(this_pce)
                combined_passenger_counting_events.append(last_pce)
            else:
                if p == 1:
                    combined_passenger_counting_events.append(last_pce)

                combined_passenger_counting_events.append(this_pce)

        # set results back to internal list
        self._passenger_counting_events = combined_passenger_counting_events