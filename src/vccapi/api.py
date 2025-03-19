from datetime import datetime
from fastapi import FastAPI

from vcclib import database
from vcclib.model import Stop
from vcclib.model import Line
from vcclib.model import Trip
from vcclib.model import StopTime
from vcclib.model import MasterDataVehicle
from vcclib.model import MasterDataObjectClass

from vcclib.model import sqlobject2dict

# init database connection
database.init()

# create fastapi instance
app = FastAPI()

# define ressouces and routes
@app.get('/stops/byLookupName/{lookup_name}')
async def stops_by_name(lookup_name):
    return Stop.lookup(lookup_name)

@app.get('/departures/byParentStopId/{parent_stop_id}')
async def departures_by_parent_stop_id(parent_stop_id):
    parent_stop_id = int(parent_stop_id)

    result = list()
    for d in Stop.departures(parent_stop_id):
        obj = {
            'stop_id': d.stop.stop_id,
            'line': sqlobject2dict(d.trip.line),
            'trip_id': d.trip.trip_id,
            'direction': d.trip.direction,
            'headsign': d.trip.headsign,
            'international_id': d.trip.international_id,
            'arrival_timestamp': d.arrival_timestamp,
            'departure_timestamp': d.departure_timestamp,
            'sequence': d.sequence
        }

        result.append(obj)

    return result

@app.get('/trips/byTripId/{trip_id}')
async def trips_by_id(trip_id):
    trip_id = int(trip_id)

    trip = Trip.select(Trip.q.trip_id == trip_id).getOne()

    stop_times_result = list()
    for st in trip.stop_times():
        stop_times_result.append({
            'stop': sqlobject2dict(st.stop),
            'arrival_timestamp': st.arrival_timestamp,
            'departure_timestamp': st.departure_timestamp,
            'sequence': st.sequence
        })

    trip_result = {
        'trip_id': trip.trip_id,
        'line': sqlobject2dict(trip.line),
        'direction': trip.direction,
        'headsign': trip.headsign,
        'international_id': trip.international_id,
        'next_trip_id': trip.next_trip_id,
        'stop_times': stop_times_result
    }

    return trip_result

@app.get('/masterdata/vehicles')
async def masterdata_vehicles():
    return [sqlobject2dict(o) for o in MasterDataVehicle.select()]

@app.get('/masterdata/objectclasses')
async def masterdata_objectclasses():
    return [sqlobject2dict(o) for o in MasterDataObjectClass.select()]

@app.post('/results/post')
async def results_post():
    pass

@app.get('/system/setup')
async def system_setup():
    pass

@app.get('/system/health')
async def system_health():
    return {
        'timestamp': int(datetime.now().timestamp())
    }