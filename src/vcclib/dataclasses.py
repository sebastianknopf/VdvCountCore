from dataclasses import dataclass
from dataclasses import field
from datetime import datetime

from typing import List

@dataclass
class Stop:
    id: int
    international_id: str|None = None
    name: str|None = None
    latitude: float = 0.0
    longitude: float = 0.0
    sequence: int = 0

    def __init__(self) -> None:
        pass

@dataclass
class CountingSequence:
    door_id: str
    area_id: str
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