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
        pass

    def begin_timestamp(self) -> int:
        min_timestamp = int(datetime.now().timestamp())

        for cs in self.counting_sequences:
            cs_timestamp = int(cs.begin_timestamp.timestamp())
            if cs_timestamp < min_timestamp:
                min_timestamp = cs_timestamp

        return min_timestamp

    def end_timestamp(self) -> int:
        max_timestamp = 0

        for cs in self.counting_sequences:
            cs_timestamp = int(cs.end_timestamp.timestamp())
            if cs_timestamp > max_timestamp:
                max_timestamp = cs_timestamp

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