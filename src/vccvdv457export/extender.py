import logging

from typing import List

from datetime import datetime
from datetime import timedelta

from vcclib.dataclasses import Trip
from vcclib.dataclasses import PassengerCountingEvent
from vcclib.dataclasses import CountingSequence

class PassengerCountingEventExtender:

    MAXIMUM_TEMPORAL_SEQUENCE_DELTA_MINUTES = 30

    def __init__(self, trip: Trip) -> None:
        self._trip = trip

    def extend(self, passenger_counting_events: List[PassengerCountingEvent]) -> List[PassengerCountingEvent]:

        result: List[PassengerCountingEvent] = list()
        result.extend(passenger_counting_events)

        for stop_time in self._trip.stop_times:

            # check if there's no PCE for this stop
            existing_passenger_counting_events: List[PassengerCountingEvent] = [pce for pce in passenger_counting_events if pce.stop is not None and pce.stop.id == stop_time.stop.id and pce.stop.sequence == stop_time.stop.sequence]
            if len(existing_passenger_counting_events) == 0:

                # generate empty PCE for this stop
                cs: CountingSequence = CountingSequence()
                cs.begin_timestamp = stop_time.departure_time if stop_time.departure_time is not None else stop_time.arrival_time
                cs.end_timestamp = stop_time.departure_time if stop_time.departure_time is not None else stop_time.arrival_time
                cs.counting_area_id = '1'
                cs.door_id = '0'
                cs.object_class = 'Adult'
                cs.count_in = 0
                cs.count_out = 0

                pce: PassengerCountingEvent = PassengerCountingEvent()
                pce.latitude = stop_time.stop.latitude
                pce.longitude = stop_time.stop.longitude
                pce.stop = stop_time.stop

                pce.counting_sequences.append(cs)

                result.append(pce)

        # sort result by stop sequence
        result.sort(key=lambda p: p.stop.sequence if p.stop is not None else p.after_stop_sequence)

        # shift temporal sequence of added PCE
        logging.info(f"Generating temporal sequence for {len(result)} PCE ...")
        result = self._ensure_temporal_sequence(result)

        return result
    
    def _ensure_temporal_sequence(self, passenger_counting_events: List[PassengerCountingEvent], min_delta_minutes: float = 0.166667) -> List[PassengerCountingEvent]:

        passenger_counting_events = passenger_counting_events.copy()
        for i in range(1, len(passenger_counting_events)):
            previous_pce: PassengerCountingEvent = passenger_counting_events[i - 1]
            current_pce: PassengerCountingEvent = passenger_counting_events[i]

            if current_pce.begin_timestamp() < previous_pce.end_timestamp():
                absolute_delta_minutes: float = self._get_absolute_delta_minutes(current_pce.begin_timestamp(), previous_pce.end_timestamp())
                if absolute_delta_minutes <= self.MAXIMUM_TEMPORAL_SEQUENCE_DELTA_MINUTES:
                    absolute_delta_minutes += min_delta_minutes
                    
                    if self._is_fixed_pce(current_pce):
                        if not self._is_fixed_pce(previous_pce):
                            self._shift_pce(previous_pce, timedelta(minutes=-max(min_delta_minutes, absolute_delta_minutes)))
                    else:
                        self._shift_pce(current_pce, timedelta(minutes=max(min_delta_minutes, absolute_delta_minutes)))
                else:
                    logging.warning(f"Ensuring temporal sequence between PCE [{i - 1}] and PCE [{i}] would require a shift of {absolute_delta_minutes}min, maximum is {self.MAXIMUM_TEMPORAL_SEQUENCE_DELTA_MINUTES}min")

        return passenger_counting_events

    def _get_absolute_delta_minutes(self, dt1: datetime, dt2: datetime) -> float:
        delta: timedelta = dt2 - dt1

        minutes: float = delta.total_seconds() / 60
        return abs(minutes)
    
    def _is_fixed_pce(self, passenger_counting_event: PassengerCountingEvent) -> bool:
        return len([cs for cs in passenger_counting_event.counting_sequences if cs.door_id != '0']) > 0
    
    def _shift_pce(self, passenger_counting_event: PassengerCountingEvent, delta: timedelta) -> None:
        timestamp: datetime = passenger_counting_event.counting_sequences[0].begin_timestamp + delta
        
        passenger_counting_event.counting_sequences[0].begin_timestamp = timestamp
        passenger_counting_event.counting_sequences[0].end_timestamp = timestamp

