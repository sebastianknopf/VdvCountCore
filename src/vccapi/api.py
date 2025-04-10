import json
import logging
import os
import pytz

from datetime import datetime
from io import BytesIO
from fastapi import FastAPI, Request, Response
from qrcode import QRCode, constants

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

@app.post('/results/post/{guid}')
async def results_post(guid, request: Request):
    
    data = await request.json()

    with open(f"/data/{guid}.json", 'w+') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

    return Response(status_code=200)

@app.get('/system/setup')
async def system_setup():
    # load data of environment variables and generate setup config
    api_scheme = os.getenv('VCC_API_SCHEME', 'http')
    api_hostname = os.getenv('VCC_API_HOSTNAME', 'localhost')
    api_port = os.getenv('VCC_API_PORT', '443')

    vcc_username = os.getenv('VCC_USERNAME', None)
    vcc_password = os.getenv('VCC_PASSWORD', None)

    if vcc_username is None or vcc_password is None:
        logging.error('Either environment variable VCC_USERNAME or VCC_PASSWORD not configured!')
        return Response(status_code=500)
    
    setup_config = [f"{api_scheme}://{vcc_username}:{vcc_password}@{api_hostname}:{api_port}/", vcc_username, vcc_password]
    setup_config = '#'.join(setup_config)
    
    # generate QR code response
    qr = QRCode(
        version=1,
        error_correction=constants.ERROR_CORRECT_L,
        box_size=10,
        border=4
    )

    qr.add_data(setup_config)
    qr.make(fit=True)

    img = qr.make_image(fill="black", back_color="white")
    imgio = BytesIO()
    img.save(imgio, format="PNG")
    imgio.seek(0)

    return Response(content=imgio.getvalue(), media_type="image/png")

@app.get('/system/health')
async def system_health():
    
    
    return {
        'timestamp': int(datetime.now().astimezone((pytz.timezone('Europe/Berlin'))).timestamp())
    }