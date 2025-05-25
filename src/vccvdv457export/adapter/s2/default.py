import logging
import os
import uuid

from datetime import datetime
from typing import Dict
from typing import List
from typing import Set

from vcclib.common import isoformattime
from vcclib.dataclasses import PassengerCountingEvent
from vcclib.dataclasses import CountingSequence
from vcclib.duckdb import DuckDB
from vcclib.xml import dict2xml

from vccvdv457export.adapter.base import BaseAdapter
from vccvdv457export.collector import PassengerCountingEventCollector

class DefaultAdapter(BaseAdapter):

    def __init__(self) -> None:
        pass

    def process(self, ddb: DuckDB, output_directory: str) -> None:
        super().process(ddb, output_directory)

        # extract PCE from loaded data
        logging.info("Extracting PCE data from local DDB ...")
        extracted_data: Dict[tuple, List[PassengerCountingEvent]] = self._extract(ddb)

        # transform each operation_day/trip_id combination into final data structure
        logging.info(f"Transforming data of {len(extracted_data.keys())} trips ...")
        
        transformed_data: List[str] = list()
        for (operation_day, trip_id), passenger_counting_events in extracted_data.items():
            transformed_data.append(
                self._transform(operation_day, trip_id, passenger_counting_events)
            )

        # export data finally
        logging.info(f"Exporting {len(transformed_data)} trips ...")
        self._export(transformed_data, output_directory)

    def _extract(self, ddb: DuckDB) -> Dict[tuple, List[PassengerCountingEvent]]:

        results: Dict[tuple, List[PassengerCountingEvent]] = dict()

        logging.info("Loading primary indicators")
        for (operation_day, trip_id), primary_device_id in ddb.get_primary_indicators().items():

            logging.info(f"Processing trip ID {trip_id} at {operation_day}, primary device is {primary_device_id}")

            # select primary data and create collector instance
            primary_data = ddb.get_data(operation_day, trip_id, primary_device_id)
            collector: PassengerCountingEventCollector = PassengerCountingEventCollector(primary_data)
            
            # select device IDs for secondary data
            for secondary_device_id in ddb.get_secondary_device_ids(operation_day, trip_id, primary_device_id):

                logging.info(f"Adding secondary data of device {secondary_device_id}")

                # select secondary data 
                secondary_data = ddb.get_data(operation_day, trip_id, secondary_device_id)
                collector.add(secondary_data)

            # call verify method to log every possible invalid dataset
            collector.verify()

            # return finally generated PCE data
            passenger_counting_events = collector.get_passenger_counting_events()

            logging.info(f"Found total {len(passenger_counting_events)} PCEs")

            results[(operation_day, trip_id)] = passenger_counting_events
        
        # finally return generated results
        return results
    
    def _transform(self, ddb: DuckDB, operation_day: int, trip_id: int, device_id: str, passenger_counting_events: List[PassengerCountingEvent]) -> str:

        # select trip details and obtain basic data
        trip_details = ddb.get_trip_details(
            operation_day,
            trip_id
        )

        vehicle_id = trip_details[0]['vehicle_id']

        direction = trip_details[0]['direction']

        line_id = trip_details[0]['line_id']
        line_international_id = trip_details[0]['line_international_id']
        line_name = trip_details[0]['line_name']

        # build results dataset
        result: dict = {
            'HeaderData': {
                'VehicleID': vehicle_id
            },
            'PassengerCountingEvent': list()
        }

        for i, pce in enumerate(passenger_counting_events):
            
            # header for each PCE
            pce_xml = {
                'HeaderCountingEvent': {
                    'QueryType': 'departure',
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
                }
            }

            # stop information
            if pce.stop is not None:
                pce_xml['StopInformation'] = {
                    'StopRef': {
                        'Value': pce.stop.id
                    },
                    'PassengerRelated': {
                        'Value': 'true'
                    }
                }
            else:
                pce_xml['StopInformation'] = {
                    'PassengerRelated': {
                        'Value': 'true'
                    }
                }
            
            # line information
            pce_xml['Line'] = {
                'LineRef': {
                    'Value': line_id
                },
                'LineNumber': {
                    'Value': line_name
                },
                'DirectionType': direction
            }
                
            # GPS position
            pce_xml['GNSS'] = {
                'GNSS_Point_Structure': {
                    'Longitude': {
                        'Degree': {
                            'Value': pce.longitude
                        }
                    },
                    'Latitude': {
                        'Degree': {
                            'Value': pce.latitude
                        }
                    },
                    'time': {
                        'Value': isoformattime(pce.end_timestamp())
                    },
                    'date': {
                        'Value': pce.end_timestamp().strftime('%Y-%m-%d')
                    },
                    'GNSS_Type': 'GPS',
                    'GNSSCoordinateSystem': 'WGS84'
                }
            }

            # resolve counting areas, door IDs and object classes
            pce_xml['CountingArea'] = list()

            counting_area_ids: Set[str] = {cs.counting_area_id for cs in pce.counting_sequences}
            door_ids: Set[str] = {cs.door_id for cs in pce.counting_sequences}
            object_classes: Set[str] = {cs.object_class for cs in pce.counting_sequences}

            for counting_area_id in counting_area_ids:
                counting_area_xml: dict = {
                    'AreaID': counting_area_id,
                    'Counting': list()
                }

                for door_id in door_ids:
                    counting_xml: dict = {
                        'DoorID': {
                            'Value': door_id
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

                    for object_class in object_classes:
                        cs: CountingSequence = next((cs for cs in pce.counting_sequences if cs.counting_area_id == counting_area_id and cs.door_id == door_id and cs.object_class == object_class), None)
                        if cs is not None:
                            
                            if 'CountInfo' not in counting_xml:
                                counting_xml['CountInfo'] = {
                                    'DoorOpenTime': {
                                        'Value': cs.begin_timestamp.isoformat()
                                    },
                                    'DoorClosingTime': {
                                        'Value': cs.end_timestamp.isoformat()
                                    }
                                }

                            count_xml: dict = {
                                'ObjectClass': object_class,
                                'In': {
                                    'Value': cs.count_in
                                },
                                'Out': {
                                    'Value': cs.count_out
                                },
                                'CountQuality': 'Regular'
                            }

                            counting_xml['Count'].append(count_xml)

                    counting_area_xml['Counting'].append(counting_xml)

                pce_xml['CountingArea'].append(counting_area_xml)

            # finally add the PCE to the complete message
            result['PassengerCountingEvent'].append(pce_xml)

        # return an XML result
        attribute_mapping: dict = {
            'HeaderCountingEvent': [
                'QueryType'
            ]
        }

        return dict2xml('PassengerCountingMessage', result, attribute_mapping)
    
    def _export(self, transformed_data: List[str], output_directory: str) -> None:   
        
        # write each dataset to a single file
        for d in transformed_data:
            output_filename: str = os.path.join(output_directory, f"{str(uuid.uuid4())}.xml")

            with open(output_filename, 'wb') as output_file:
                output_file.write(b'<?xml version="1.0" encoding="UTF-8" ?>\n')
                output_file.write(d)