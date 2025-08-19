import logging
import os

from datetime import datetime
from typing import Dict
from typing import List
from typing import Set
from typing import Tuple
from xmltodict import unparse

from vcclib.dataclasses import PassengerCountingEvent
from vcclib.dataclasses import CountingSequence
from vcclib.dataclasses import Trip
from vcclib.dataclasses import Stop
from vcclib.duckdb import DuckDB

from vccvdv457export.adapter.base import BaseAdapter
from vccvdv457export.collector import PassengerCountingEventCollector
from vccvdv457export.extender import PassengerCountingEventExtender

class DefaultAdapter(BaseAdapter):

    def __init__(self, reports_archive_name: str = '', reports_create: bool = False) -> None:
        super().__init__(reports_archive_name, reports_create)

    def process(self, ddb: DuckDB, output_directory: str, dubious_output_directory: str) -> None:
        super().process(ddb, output_directory, dubious_output_directory)

        # extract PCE from loaded data
        logging.info("Extracting PCE data from local DDB ...")
        extracted_data: Dict[tuple, List[PassengerCountingEvent]] = self._extract(ddb)

        # transform each operation_day/trip_id combination into final data structure
        logging.info(f"Transforming data of {len(extracted_data.keys())} trips ...")

        transformed_data: Dict[tuple, str] = dict()
        for (operation_day, trip_id, vehicle_id), passenger_counting_events in extracted_data.items():
            key, value = self._transform(ddb, operation_day, trip_id, vehicle_id, passenger_counting_events)
            transformed_data[key] = value

        # export data finally
        logging.info(f"Exporting {len(transformed_data)} trips ...")
        self._export(transformed_data, output_directory, dubious_output_directory)

    def _extract(self, ddb: DuckDB) -> Dict[tuple, List[PassengerCountingEvent]]:
        
        results: Dict[tuple, List[PassengerCountingEvent]] = dict()

        logging.info("Loading primary indicators")
        for (operation_day, trip_id, vehicle_id), primary_device_id in ddb.get_primary_indicators().items():

            logging.info(f"Processing trip ID {trip_id} with vehicle ID {vehicle_id} at {operation_day}, primary device is {primary_device_id}")

            # select primary data and create collector instance
            primary_data = ddb.get_data(operation_day, trip_id, vehicle_id, primary_device_id)
            collector: PassengerCountingEventCollector = PassengerCountingEventCollector(primary_data, primary_device_id)
            
            # select device IDs for secondary data
            for secondary_device_id in ddb.get_secondary_device_ids(operation_day, trip_id, vehicle_id, primary_device_id):

                logging.info(f"Adding secondary data of device {secondary_device_id}")

                # select secondary data 
                secondary_data = ddb.get_data(operation_day, trip_id, vehicle_id, secondary_device_id)
                collector.add(secondary_data, secondary_device_id, False)

            # call verify method to log every possible invalid dataset
            collector.verify()

            # return finally generated PCE data
            passenger_counting_events = collector.get_passenger_counting_events()

            logging.info(f"Found total {len(passenger_counting_events)} PCEs")

            results[(operation_day, trip_id, vehicle_id)] = passenger_counting_events
        
        # finally return generated results
        return results

    def _transform(self, ddb: DuckDB, operation_day: int, trip_id: int, vehicle_id: str, passenger_counting_events: List[PassengerCountingEvent]) -> Tuple[tuple, str]:
        
        # select trip details and obtain basic data
        trip: Trip = self.load_trip_details(ddb, operation_day, trip_id, vehicle_id)

        origin: int = trip.stop_times[0].stop.parent_id
        destination: int = trip.stop_times[-1].stop.parent_id
        
        departure_time: datetime = trip.stop_times[0].departure_time
        destination_time: datetime = trip.stop_times[-1].arrival_time

        direction = trip.direction

        line_id = trip.line.id
        line_international_id = trip.line.international_id
        line_name = trip.line.name

        # update unmatched PCEs to their corresponding stop
        passenger_counting_events = self._update_unmatched_pces(trip, passenger_counting_events)

        # extend PCEs to nominal stops
        extender: PassengerCountingEventExtender = PassengerCountingEventExtender(trip)
        passenger_counting_events = extender.extend(passenger_counting_events)

        # build results dataset
        result: dict = {
            'PassengerCountingServiceJourney': {
                'HeaderServiceJourney': {
                    'ServiceJourneyID': trip_id,
                    'DataType': 'RawData',
                    'ServiceJourneyDepartureTime': departure_time.isoformat(),
                    'ServiceJourneyDestinationTime': destination_time.isoformat(),
                    'Origin': origin,
                    'Destination': destination,
                    'Line': {
                        'LineRef': {
                            'Value': line_id
                        },
                        'LineName': {
                            'Value': line_name,
                            'Language': 'DE'
                        },
                        'DirectionType': direction
                    }
                },
                'PassengerCountingMessage': {
                    'HeaderData': {
                        'TypeOfSurvey': 'manual',
                        'AllVehiclesOfThisJourney': {
                            'Value': 'false'
                        },
                        'AllCountingAreas': {
                            'Value': 'false'
                        },
                        'VehicleID': vehicle_id
                    },
                    'PassengerCountingEvent': list()
                }
            }
        }

        run_through_door_id: str = os.getenv('VCC_VDV457_EXPORT_RUN_THROUGH_DOOR_ID', '0')
        for i, pce in enumerate(passenger_counting_events):

            pce_xml = {
                'StopInformation': {
                    'StopStatus': 'normal',
                    'StopRef': {
                        'Value': pce.stop.parent_id
                    },
                    'StopName': {
                        'Value': pce.stop.name,
                        'Language': 'DE'
                    }
                },
                'CountingArea': list()
            }

            counting_area_ids: Set[str] = {cs.counting_area_id for cs in pce.counting_sequences}
            door_ids: Set[str] = {cs.door_id for cs in pce.counting_sequences}
            object_classes: Set[str] = {cs.object_class for cs in pce.counting_sequences}

            # create counting sequences ...
            for counting_area_id in counting_area_ids:
                counting_area_xml: dict = {
                    'AreaID': counting_area_id,
                    'HeaderCounting': {
                        '@QueryType': 'departure',
                        'SequentialNumber': i + 1,
                        'TimeStamp': {
                            'Value': pce.end_timestamp().isoformat()
                        },
                        'TimeStampEventStart': {
                            'Value': pce.begin_timestamp().isoformat()
                        },
                        'TimeStampEventEnd': {
                            'Value': pce.end_timestamp().isoformat()
                        }
                    },
                    'Counting': list()
                }

                for door_id in door_ids:
                    counting_xml: dict = {
                        'DoorID': {
                            'Value': door_id if not pce.is_run_through() else run_through_door_id
                        },
                        'DoorState': {
                            'OpenState': {
                                'Value': 'AllDoorsClosed'
                            },
                            'OperationState': {
                                'Value': 'Normal'
                            }
                        },
                        'Count': list()
                    }

                    # sum up in and out per object class
                    for object_class in object_classes:

                        cs: CountingSequence = next((cs for cs in pce.counting_sequences if cs.counting_area_id == counting_area_id and cs.door_id == door_id and cs.object_class == object_class), None)
                        if cs is not None:
                            
                            count_xml: dict = {
                                'ObjectClass': object_class,
                                'In': {
                                    'Value': cs.count_in
                                },
                                'Out': {
                                    'Value': cs.count_out
                                }
                            }

                            counting_xml['Count'].append(count_xml)

                    counting_area_xml['Counting'].append(counting_xml)

                pce_xml['CountingArea'].append(counting_area_xml)

            # finally add the PCE to the complete message
            result['PassengerCountingServiceJourney']['PassengerCountingMessage']['PassengerCountingEvent'].append(pce_xml)

        # return an XML result
        xml = unparse({
            'PassengerCountingServiceBGS_457-3.GetAllDataResponse': result
        }, pretty=True)

        return (operation_day, trip_id, vehicle_id), xml

    def _update_unmatched_pces(self, trip: Trip, passenger_counting_events: List[PassengerCountingEvent]) -> List[PassengerCountingEvent]:

        logging.info(f"Updating unmatched PCEs ...")

        # 1. Update all PCEs with after_stop_sequence != -1 to the NEXT stop
        # see #30 for details
        for pce in passenger_counting_events:
            if pce.after_stop_sequence != -1:
                stop_sequence: int = pce.after_stop_sequence
                if len(trip.stop_times) > stop_sequence:
                    stop: Stop = trip.stop_times[stop_sequence].stop

                    pce.after_stop_sequence = -1
                    pce.stop = stop

        # 2. Group all PCEs by their stop with reference to the nominal stop time
        matched_passenger_counting_events: List[PassengerCountingEvent] = list()

        stop_sequences: Set[int] = {pce.stop.sequence for pce in passenger_counting_events if pce.after_stop_sequence == -1}
        for s in stop_sequences:
            matching_pces: List[PassengerCountingEvent] = [pce for pce in passenger_counting_events if pce.stop is not None and pce.stop.sequence == s]
            if len(matching_pces) == 1:
                matched_passenger_counting_events.append(matching_pces[0])
            elif len(matching_pces) > 1:
                # filter on all real (not run-through!) PCEs 
                # see #28 for more information
                matching_pces = [pce for pce in matching_pces if not pce.is_run_through()]

                # then map all remaining PCEs together to one
                primary_pce: PassengerCountingEvent = matching_pces[0]
                for i in range(1, len(matching_pces)):
                    primary_pce.combine(matching_pces[i], False)

                matched_passenger_counting_events.append(primary_pce)       
        
        return sorted(matched_passenger_counting_events, key=lambda p: p.end_timestamp())