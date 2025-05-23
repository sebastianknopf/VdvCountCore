from dataclasses import dataclass
from dataclasses import field
from datetime import datetime

from typing import List

@dataclass
class Stop:
    id: int
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
        for cs in pce.counting_sequences:
            self.counting_sequences.append(cs)

    def intersects(self, pce: 'PassengerCountingEvent') -> bool:
        
        # check if stop ID and sequence are both the same
        if not (self.stop is not None and pce.stop is not None and self.stop.id == pce.stop.id and self.stop.sequence == pce.stop.sequence):
            return False
        
        # check if after_stop_sequence is the same
        if not (self.after_stop_sequence != -1 and self.after_stop_sequence == pce.after_stop_sequence):
            return False
        
        return True

    def begin_timestamp(self) -> datetime:
        min_timestamp = datetime(2500, 1, 1)

        for cs in self.counting_sequences:
            if cs.begin_timestamp is not None:
                if cs.begin_timestamp < min_timestamp:
                    min_timestamp = cs.begin_timestamp

        return min_timestamp

    def end_timestamp(self) -> datetime:
        max_timestamp = datetime(1900, 1, 1)

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