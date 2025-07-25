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
class Line:
    id: int
    international_id: str
    name: str

    def __init__(self) -> None:
        pass

@dataclass
class StopTime:
    arrival_time: datetime|None
    departure_time: datetime|None
    stop: Stop

    def __init__(self) -> None:
        pass

@dataclass    
class Trip:
    id: int
    vehicle_id: int
    direction: int
    line: Line
    international_id: str|None = None
    stop_times: List[StopTime] = field(default_factory=list)

    def __init__(self) -> None:
        self.stop_times = list()

@dataclass
class CountingSequence:
    door_id: str
    counting_area_id: str
    object_class: str
    begin_timestamp: datetime
    end_timestamp: datetime
    count_in: int = 0
    count_out: int = 0
    device_id: str|None = None

    def __init__(self) -> None:
        pass

@dataclass
class PassengerCountingEvent:
    latitude: float = 0.0
    longitude: float = 0.0
    after_stop_sequence: int = -1
    stop: Stop|None = None
    counting_sequences: List[CountingSequence] = field(default_factory=list)
    device_id: str|None = None

    def __init__(self) -> None:
        self.counting_sequences = list()

    def combine(self, pce: 'PassengerCountingEvent', fail_on_existing_door_id_of_different_device:bool = True) -> None:
        for counting_sequence in pce.counting_sequences:
            # see #48/49: check whether the same door ID has been delivered by a different device yet
            # if so, throw an exception if fail_on_existing_door_id is True
            existing_counting_seqeunce: CountingSequence = next((cs for cs in self.counting_sequences if cs.counting_area_id == counting_sequence.counting_area_id and cs.door_id == counting_sequence.door_id and cs.object_class == counting_sequence.object_class), None)
            if existing_counting_seqeunce is not None:
                #"""fail_on_existing_door_id_of_different_device and"""
                if counting_sequence.door_id != '0' and existing_counting_seqeunce.device_id != counting_sequence.device_id:
                    raise ValueError(f"CountingSequence with DoorID {counting_sequence.door_id} already exists for CountingAreaID {counting_sequence.counting_area_id} and ObjectClass {counting_sequence.object_class} at StopID {self.stop.id} and StopSequence {self.stop.sequence}, recorded by DeviceID {self.device_id} and DeviceID {pce.device_id}")
            
                existing_counting_seqeunce.count_in += counting_sequence.count_in
                existing_counting_seqeunce.count_out += counting_sequence.count_out
            else:
                self.counting_sequences.append(counting_sequence)

        # see #48/#49, check if there're CS with door ID 0 and also other door IDs
        # if so, remove the CS with door ID 0
        num_cs_door_0: int = len([cs for cs in self.counting_sequences if cs.door_id == '0'])
        num_cs_door_x: int = len([cs for cs in self.counting_sequences if cs.door_id != '0'])
        if num_cs_door_0 > 0 and num_cs_door_x > 0:
            self.counting_sequences = [cs for cs in self.counting_sequences if cs.door_id != '0']

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

        if consider_time and not (self.is_run_through() and pce.is_run_through()):
            if self.begin_timestamp() <= pce.end_timestamp() and pce.begin_timestamp() <= self.end_timestamp():
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
    
    def is_run_through(self) -> bool:
        counting_sequence: CountingSequence = self.counting_sequences[0] if len(self.counting_sequences) > 0 else None
        if counting_sequence is not None:
            return counting_sequence.door_id == '0' and counting_sequence.begin_timestamp == counting_sequence.end_timestamp
        
        return False
    
    def __repr__(self) -> str:
        if self.stop is not None:
            return f"StopID={self.stop.id}, StopSequence={self.stop.sequence}, Begin={self.begin_timestamp().strftime('%Y-%m-%d %H:%M:%S')}, End={self.end_timestamp().strftime('%Y-%m-%d %H:%M:%S')}, Latitude={self.latitude}, Longitude={self.longitude}, In={self.count_in()}, Out={self.count_out()}"
        else:
            return f"AfterStopSequence={self.after_stop_sequence}, Begin={self.begin_timestamp().strftime('%Y-%m-%d %H:%M:%S')}, End={self.end_timestamp().strftime('%Y-%m-%d %H:%M:%S')}, Latitude={self.latitude}, Longitude={self.longitude}, In={self.count_in()}, Out={self.count_out()}"