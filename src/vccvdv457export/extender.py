
from typing import List

from vcclib.dataclasses import Trip
from vcclib.dataclasses import PassengerCountingEvent
from vcclib.dataclasses import CountingSequence

class PassengerCountingEventExtender:

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

        return result