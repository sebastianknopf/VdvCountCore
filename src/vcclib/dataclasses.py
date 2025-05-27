from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from datetime import timezone

from typing import List

@dataclass
class Stop:
    id: int
    parent_id: int
    international_id: str|None = None
    latitude: float = 0.0
    longitude: float = 0.0
    name: str|None = None
    sequence: int = 0

    def __init__(self) -> None:
        pass

@dataclass
class CountingSequence:
    door_id: str
    counting_area_id: str
    object_class: str
    begin_timestamp: datetime
    end_timestamp: datetime
    count_in: int = 0
    count_out: int = 0

    def __init__(self) -> None:
        pass

@dataclass
class PassengerCountingEvent:
    latitude: float = 0.0
    longitude: float = 0.0
    after_stop_sequence: int = -1
    stop: Stop|None = None
    counting_sequences: List[CountingSequence] = field(default_factory=list)

    def __init__(self) -> None:
        self.counting_sequences = list()

    def combine(self, pce: 'PassengerCountingEvent') -> None:
        for counting_sequence in pce.counting_sequences:
            existing_cs: CountingSequence = next((cs for cs in self.counting_sequences if cs.counting_area_id == counting_sequence.counting_area_id and cs.door_id == counting_sequence.door_id and cs.object_class == counting_sequence.object_class), None)
            if existing_cs is not None:
                existing_cs.count_in += counting_sequence.count_in
                existing_cs.count_out += counting_sequence.count_out
            else:
                self.counting_sequences.append(counting_sequence)

    def intersects(self, pce: 'PassengerCountingEvent', consider_position: bool = True, consider_time: bool = True) -> bool:
        # check if stop ID and sequence or after_stop_sequence are the same
        position_intersection: bool = False
        
        if consider_position:
            if self.stop is not None and pce.stop is not None and self.stop.id == pce.stop.id and self.stop.sequence == pce.stop.sequence:
                position_intersection = True
            elif self.after_stop_sequence != -1 and self.after_stop_sequence == pce.after_stop_sequence:
                position_intersection = True
        else:
            position_intersection = True

        # check if time of PCEs are intersecting
        time_intersection: bool = False

        if consider_time:
            if self.begin_timestamp() <= pce.begin_timestamp() <= self.end_timestamp():
                time_intersection = True
        else:
            time_intersection = True
        
        return position_intersection and time_intersection

    def begin_timestamp(self) -> datetime:
        min_timestamp = datetime(2500, 1, 1, tzinfo=timezone.utc)

        for cs in self.counting_sequences:
            if cs.begin_timestamp is not None:
                if cs.begin_timestamp < min_timestamp:
                    min_timestamp = cs.begin_timestamp

        return min_timestamp

    def end_timestamp(self) -> datetime:
        max_timestamp = datetime(1900, 1, 1, tzinfo=timezone.utc)

        for cs in self.counting_sequences:
            if cs.end_timestamp is not None:
                if cs.end_timestamp > max_timestamp:
                    max_timestamp = cs.end_timestamp

        return max_timestamp
    
    def count_in(self) -> int:
        sum = 0
        for cs in self.counting_sequences:
            sum = sum + cs.count_in

        return sum
    
    def count_out(self) -> int:
        sum = 0
        for cs in self.counting_sequences:
            sum = sum + cs.count_out

        return sum
    
    def __repr__(self):
        if self.stop is not None:
            return f"StopID={self.stop.id}, StopSequence={self.stop.sequence}, Begin={self.begin_timestamp().strftime('%Y-%m-%d %H:%M:%S')}, End={self.end_timestamp().strftime('%Y-%m-%d %H:%M:%S')}, Latitude={self.latitude}, Longitude={self.longitude}, In={self.count_in()}, Out={self.count_out()}"
        else:
            return f"AfterStopSequence={self.after_stop_sequence}, Begin={self.begin_timestamp().strftime('%Y-%m-%d %H:%M:%S')}, End={self.end_timestamp().strftime('%Y-%m-%d %H:%M:%S')}, Latitude={self.latitude}, Longitude={self.longitude}, In={self.count_in()}, Out={self.count_out()}"