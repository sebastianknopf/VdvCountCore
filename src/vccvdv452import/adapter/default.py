import logging
import os

from datetime import datetime

from vcclib import database
from vcclib.model import Stop
from vcclib.model import Line
from vcclib.model import Trip
from vcclib.model import StopTime
from vcclib.x10 import read_x10_file, X10File
from vccvdv452import.adapter.base import BaseAdapter

class DefaultAdapter(BaseAdapter):

    def __init__(self) -> None:
        pass

    def process(self, input_directory: str) -> None:

        # verify input directory and files present
        self._verify(input_directory)
        
        # define processing variables
        batch_size = 2500

        # clear database before insert
        logging.info('Clearing database ...')
        
        Stop.deleteMany(where=None)
        Line.deleteMany(where=None)
        Trip.deleteMany(where=None)
        StopTime.deleteMany(where=None)

        # load network data ...
        logging.info('Loading network data ...')

        # load and import stop objects
        stop_index = dict()

        transaction = database.connection().transaction()
        transaction_count = 0

        x10_rec_ort = self._internal_read_x10_file(input_directory, 'rec_ort.x10')
        for i, record in enumerate(x10_rec_ort.records):
            try:
                if record['ONR_TYP_NR'] == 1:
                    stop_id = record['ORT_NR']
                    name = record['ORT_REF_ORT_NAME']
                    latitude = self._convert_coordinate(record['ORT_POS_BREITE'])
                    longitude = self._convert_coordinate(record['ORT_POS_LAENGE'])
                    parent_id = record['ORT_REF_ORT']

                    if 'HST_NR_INTERNATIONAL' in record:
                        international_id = record['HST_NR_INTERNATIONAL']
                    elif 'ORT_GLOBAL_ID' in record:
                        international_id = record['ORT_GLOBAL_ID']
                    else:
                        international_id = None

                    stop_index[stop_id] = Stop(
                        stop_id=stop_id,
                        name=name,
                        latitude=latitude,
                        longitude=longitude,
                        international_id=international_id,
                        parent_id=parent_id,
                        connection=transaction
                    )

                if transaction_count >= batch_size or i >= len(x10_rec_ort.records) - 1:
                    transaction.commit()

                    transaction = database.connection().transaction()
                    transaction_count = 0

            except Exception as ex:
                transaction.rollback()

                if not i >= len(x10_rec_ort.records):
                    transaction = database.connection().transaction()

                logging.exception(ex)

        x10_rec_ort.close()

        # load and import line objects
        line_index = dict()
        line_direction_index = dict()

        transaction = database.connection().transaction()
        transation_count = 0

        x10_rec_lid = self._internal_read_x10_file(input_directory, 'rec_lid.x10')
        for i, record in enumerate(x10_rec_lid.records):
            try:
                line_id = record['LI_NR']
                line_variant_id = record['STR_LI_VAR']
                direction = record['LI_RI_NR']
                name = record['LI_KUERZEL']
                
                if 'LinienID' in record:
                    international_id = record['LinienID']
                else:
                    international_id = None

                if (line_id, line_variant_id) not in line_direction_index:
                    line_direction_index[(line_id, line_variant_id)] = direction

                if line_id not in line_index:
                    line_index[line_id] = Line(
                        line_id=line_id, 
                        name=name, 
                        connection=transaction
                    )

                    transation_count = transation_count + 1

                if transation_count >= batch_size or i >= len(x10_rec_lid.records) - 1:
                    transaction.commit()

                    transaction = database.connection().transaction()
                    transation_count = 0

            except Exception as ex:
                transaction.rollback()

                if not i >= len(x10_rec_lid.records) - 1:
                    transaction = database.connection().transaction()

                logging.exception(ex)
    
        x10_rec_lid.close()

        # load timetable information data ...  
        logging.info('Loading timetable information data ...')

        daytype = None
        x10_firmenkalender = self._internal_read_x10_file(input_directory, 'firmenkalender.x10')
        for record in x10_firmenkalender.records:
            if datetime.now().strftime('%Y%m%d') == str(record['BETRIEBSTAG']):
                daytype = record['TAGESART_NR']
                break

        x10_firmenkalender.close()

        if daytype == None:
            raise ValueError(f"No valid daytype number found for {datetime.now().strftime('%Y%m%d')}")
        
        logging.info(f"Using daytype number {daytype}")

        # load routes for each line
        line_route_index = dict()
        x10_lid_verlauf = self._internal_read_x10_file(input_directory, 'lid_verlauf.x10')
        for record in x10_lid_verlauf.records:
            if record['ONR_TYP_NR'] == 1:
                line_id = record['LI_NR']
                line_variant_id = record['STR_LI_VAR']
                stop_nr = record['ORT_NR']

                if (line_id, line_variant_id) not in line_route_index:
                    line_route_index[(line_id, line_variant_id)] = list()

                line_route_index[(line_id, line_variant_id)].append(stop_nr)

        x10_lid_verlauf.close()

        # load time demand types
        time_demand_type_index = dict()
        x10_sel_fzt_feld = self._internal_read_x10_file(input_directory, 'sel_fzt_feld.x10')
        for record in x10_sel_fzt_feld.records:
            if record['ONR_TYP_NR'] == 1 and record['SEL_ZIEL_TYP'] == 1:
                tdt_id = record['FGR_NR']
                start_stop_id = record['ORT_NR']
                dest_stop_id = record['SEL_ZIEL']
                time_demand_seconds = record['SEL_FZT']

                if tdt_id not in time_demand_type_index:
                    time_demand_type_index[tdt_id] = dict()

                if start_stop_id not in time_demand_type_index[tdt_id]:
                    time_demand_type_index[tdt_id][start_stop_id] = dict()

                if dest_stop_id not in time_demand_type_index[tdt_id][start_stop_id]:
                    time_demand_type_index[tdt_id][start_stop_id][dest_stop_id] = dict()

                time_demand_type_index[tdt_id][start_stop_id][dest_stop_id] = time_demand_seconds

        x10_sel_fzt_feld.close()

        # load stop based waiting time index
        stop_waiting_time_index = dict()

        x10_ort_hztf = self._internal_read_x10_file(input_directory, 'ort_hztf.x10')
        for record in x10_ort_hztf.records:
            if record['ONR_TYP_NR'] == 1:
                tdt_id = record['FGR_NR']
                stop_id = record['ORT_NR']
                waiting_time_seconds = record['HP_HZT']

                if tdt_id not in stop_waiting_time_index:
                    stop_waiting_time_index[tdt_id] = dict()
                    
                stop_waiting_time_index[tdt_id][stop_id] = waiting_time_seconds

        x10_ort_hztf.close()

        # load trip based waiting time index
        trip_waiting_time_index = dict()

        x10_rec_frt_hzt = self._internal_read_x10_file(input_directory, 'rec_frt_hzt.x10')
        for record in x10_rec_frt_hzt.records:
            if record['ONR_TYP_NR'] == 1:
                trip_id = record['FRT_FID']
                stop_id = record['ORT_NR']
                waiting_time_seconds = record['FRT_HZT_ZEIT']

                if trip_id not in trip_waiting_time_index:
                    trip_waiting_time_index[trip_id] = dict()

                trip_waiting_time_index[trip_id][stop_id] = waiting_time_seconds

        x10_rec_frt_hzt.close()

        # load and generate trips
        logging.info('Generating trips ...')

        trip_index = dict()

        transaction = database.connection().transaction()
        transaction_count = 0

        x10_rec_frt = self._internal_read_x10_file(input_directory, 'rec_frt.x10')
        for i, record in enumerate(x10_rec_frt.records):
            try:
                if record['TAGESART_NR'] == daytype:

                    trip_id = record['FRT_FID']
                    line_id = record['LI_NR']
                    international_id = None

                    _line_variant_id = record['STR_LI_VAR']
                    _tdt_id = record['FGR_NR']
                    _last_timestamp = int(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()) + record['FRT_START']
                    _intermediate_stops = line_route_index[(line_id, _line_variant_id)]

                    direction = line_direction_index[(line_id, _line_variant_id)]

                    trip = Trip(
                        trip_id=trip_id, 
                        line=line_index[line_id],
                        direction=direction,
                        international_id=international_id,
                        connection=transaction
                    )

                    for s in range(0, len(_intermediate_stops)):
                        stop_id = _intermediate_stops[s]
                        arrival_timestamp = _last_timestamp
                        departure_timestamp = arrival_timestamp

                        if _tdt_id in stop_waiting_time_index and stop_id in stop_waiting_time_index[_tdt_id]:
                            departure_timestamp = departure_timestamp + stop_waiting_time_index[_tdt_id][stop_id]

                        if trip_id in trip_waiting_time_index and stop_id in trip_waiting_time_index[trip_id]:
                            departure_timestamp = departure_timestamp + trip_waiting_time_index[trip_id][stop_id]

                        StopTime(
                            stop=stop_index[stop_id],
                            trip=trip,
                            arrival_timestamp=arrival_timestamp,
                            departure_timestamp=departure_timestamp,
                            sequence=s + 1,
                            connection=transaction
                        )

                        if s < len(_intermediate_stops) - 1:
                            next_stop_id = _intermediate_stops[s + 1]

                            _last_timestamp = departure_timestamp + time_demand_type_index[_tdt_id][stop_id][next_stop_id]

                    trip.headsign = stop_index[_intermediate_stops[-1]].name

                    trip_index[trip.trip_id] = trip
                    transaction_count = transaction_count + 1

                if transaction_count >= batch_size or i >= len(x10_rec_frt.records) - 1:
                    transaction.commit()

                    logging.info(f"Imported batch of {transaction_count} trips")

                    transaction = database.connection().transaction()
                    transaction_count = 0

            except Exception as ex:
                transaction.rollback()

                if not i >= len(x10_rec_frt.records) - 1:
                    transaction = database.connection().transaction()

                logging.exception(ex)

        logging.info(f"Imported {len(trip_index)} unique trips for operation day {datetime.now().strftime('%Y%m%d')}")
    
    def _verify(self, input_directory:str) -> None:
        logging.info(f"Verifying files in input directory {input_directory} ...")

        x10_rec_ort_filename = os.path.join(input_directory, 'rec_ort.x10')
        if not os.path.exists(x10_rec_ort_filename) or not os.path.isfile(x10_rec_ort_filename):
            raise FileNotFoundError(f"Required file {x10_rec_ort_filename} not found")
        
        x10_rec_lid_filename = os.path.join(input_directory, 'rec_lid.x10')
        if not os.path.exists(x10_rec_lid_filename) or not os.path.isfile(x10_rec_lid_filename):
            raise FileNotFoundError(f"Required file {x10_rec_lid_filename} not found")
        
        x10_lid_verlauf_filename = os.path.join(input_directory, 'lid_verlauf.x10')
        if not os.path.exists(x10_lid_verlauf_filename) or not os.path.isfile(x10_lid_verlauf_filename):
            raise FileNotFoundError(f"Required file {x10_lid_verlauf_filename} not found")
        
        x10_sel_fzt_feld_filename = os.path.join(input_directory, 'sel_fzt_feld.x10')
        if not os.path.exists(x10_sel_fzt_feld_filename) or not os.path.isfile(x10_sel_fzt_feld_filename):
            raise FileNotFoundError(f"Required file {x10_sel_fzt_feld_filename} not found")
        
        x10_rec_frt_filename = os.path.join(input_directory, 'rec_frt.x10')
        if not os.path.exists(x10_rec_frt_filename) or not os.path.isfile(x10_rec_frt_filename):
            raise FileNotFoundError(f"Required file {x10_rec_frt_filename} not found")

    def _internal_read_x10_file(self, input_directory: str, x10filename: str) -> X10File:
        for entry in os.listdir(input_directory):
            if entry.lower() == x10filename.lower():
                x10filename = entry
                break
        
        x10filename = os.path.join(input_directory, x10filename)

        if not os.path.exists(x10filename) or not os.path.isfile(x10filename):
            raise FileNotFoundError(f"File {x10filename} not found!")
        
        logging.info(f"Reading {x10filename} ...")

        return read_x10_file(x10filename, encoding='cp1252')

    def _convert_coordinate(self, input: int) -> float:
        input = str(input)
        if len(input) >= 7:
            degree_angle_coordinate = input.replace('-', '').rjust(10, '0')

            degrees = float(degree_angle_coordinate[:3])
            minutes = float(degree_angle_coordinate[3:5])
            seconds = float(degree_angle_coordinate[5:]) / 1000.0

            degrees = abs(degrees)
            sign = -1 if input.startswith('-') else 1
            return sign * (degrees + (minutes / 60) + (seconds / 3600))
    
        return 0.0