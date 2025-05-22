import re

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from difflib import SequenceMatcher
from sqlobject import *
from sqlobject.sqlbuilder import Select
from typing import List

from vcclib import database

@dataclass
class CountedStop:
    id: int
    international_id: str = None
    name: str
    latitude: float = 0.0
    longitude: float = 0.0
    sequence: int

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
    counted_stop: CountedStop = None
    counting_sequences: List[CountingSequence] = field(default_factory=list)

    def __init__(self) -> None:
        pass

class Stop(SQLObject):
    stop_id = IntCol()
    name = StringCol()
    latitude = FloatCol()
    longitude = FloatCol()
    international_id = StringCol(default=None)
    parent_id = IntCol()

    @classmethod
    def lookup(cls, lookup_name:str):
        def normalize(input:str) -> str:
            normalized = input.lower().strip()
            normalized = re.sub(r"[^a-z0-9äöüß\s]", '', normalized)
            replacements = {
                'hbf': 'hauptbahnhof', 
                'bf': 'bahnhof'
            }
            
            for short, full in replacements.items():
                normalized = normalized.replace(short, full)

            return normalized
        
        result = list()

        query = Select((
            Stop.q.parent_id, 
            Stop.q.name, 
            f"AVG({Stop.q.latitude})", 
            f"AVG({Stop.q.longitude})"
        ), groupBy=[Stop.q.parent_id, Stop.q.name])
        
        query = database.connection().sqlrepr(query)

        for s in database.connection().queryAll(query):
            obj = dict()
            obj['parent_id'] = s[0]
            obj['name'] = s[1]
            obj['latitude'] = s[2]
            obj['longitude'] = s[3]
            obj['similarity'] = SequenceMatcher(None, normalize(s[1]), normalize(lookup_name)).ratio()

            if obj['similarity'] > 0.5:
                result.append(obj)

        return sorted(result, key=lambda s: s['similarity'], reverse=True)[:30]

    @classmethod
    def departures(cls, parent_stop_id:int):
        stops = cls.select(Stop.q.parent_id == parent_stop_id)

        return StopTime.select((IN(StopTime.q.stop, stops)) & (StopTime.q.departure_timestamp != None)).orderBy(StopTime.q.departure_timestamp)

class Line(SQLObject):
    line_id = IntCol()
    name = StringCol()
    international_id = StringCol(default=None)
    type = StringCol(default=None)

class Trip(SQLObject):
    trip_id = IntCol()
    line = ForeignKey('Line', cascade=True)
    direction = IntCol()
    headsign = StringCol(default=None)
    international_id = StringCol(default=None)
    operation_day = IntCol()
    next_trip_id = IntCol(default=None)

    def stop_times(self):
        return StopTime.select(StopTime.q.trip == self).orderBy(StopTime.q.sequence)

class StopTime(SQLObject):
    trip = ForeignKey('Trip', cascade=True)
    stop = ForeignKey('Stop', cascade=True)
    arrival_timestamp = IntCol()
    departure_timestamp = IntCol(default=None)
    sequence = IntCol()

class MasterDataVehicle(SQLObject):
    name = StringCol()
    num_doors = IntCol()

class MasterDataObjectClass(SQLObject):
    name = StringCol()
    description = StringCol(default=None)

def sqlobject2dict(obj:SQLObject) -> dict:
    return {col: getattr(obj, col) for col in obj.sqlmeta.columns}
