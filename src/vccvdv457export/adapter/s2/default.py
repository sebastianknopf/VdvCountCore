import logging
import os

from datetime import datetime
from typing import Dict
from typing import List
from typing import Set
from typing import Tuple
from xmltodict import unparse

from vcclib.common import isoformattime
from vcclib.dataclasses import PassengerCountingEvent
from vcclib.dataclasses import CountingSequence
from vcclib.dataclasses import Trip
from vcclib.duckdb import DuckDB
from vcclib.version import version

from vccvdv457export.adapter.base import BaseAdapter
from vccvdv457export.collector import PassengerCountingEventCollector
from vccvdv457export.extender import PassengerCountingEventExtender

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
        
        transformed_data: Dict[tuple, str] = dict()
        for (operation_day, trip_id, vehicle_id), passenger_counting_events in extracted_data.items():
            key, value = self._transform(ddb, operation_day, trip_id, vehicle_id, passenger_counting_events)
            transformed_data[key] = value

        # export data finally
        logging.info(f"Exporting {len(transformed_data)} trips ...")
        self._export(transformed_data, output_directory)

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
                collector.add(secondary_data, secondary_device_id)

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

        direction = trip.direction

        line_id = trip.line.id
        line_international_id = trip.line.international_id
        line_name = trip.line.name

        # extend PCEs to nominal stops
        extender: PassengerCountingEventExtender = PassengerCountingEventExtender(trip)
        passenger_counting_events = extender.extend(passenger_counting_events)

        # build results dataset
        result: dict = {
            'HeaderData': {
                'VehicleID': vehicle_id,
                'APC-Device': {
                    'DeviceSpecification': {
                        'DeviceClass': 'APC',
                        'DeviceID': {
                            'Value': 'VdvCountCore'
                        }
                    },
                    'DeviceState': 'running',
                    'SoftwareVersion': {
                        'DataType': {
                            'Value': 'firmware'
                        },
                        'VersionRef': {
                            'Value': version
                        }
                    }
                }
            },
            'PassengerCountingEvent': list()
        }

        run_through_door_id: str = os.getenv('VCC_VDV457_EXPORT_RUN_THROUGH_DOOR_ID', '0')
        for i, pce in enumerate(passenger_counting_events):
            
            # header for each PCE
            pce_xml = {
                'HeaderCountingEvent': {
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
                }
            }

            # journey info
            pce_xml['JourneyInfo'] = {
                'BlockRef': 0,
                'ServiceJourneyRef': trip_id
            }
            
            # line information
            pce_xml['Line'] = {
                'LineRef': {
                    'Value': line_id
                },
                'LineName': {
                    'Value': line_name,
                    'Language': 'DE'
                },
                'DirectionType': direction
            }

            # stop information
            if pce.stop is not None:
                pce_xml['StopInformation'] = {
                    'StopIndex': {
                        'Value': pce.stop.sequence
                    },
                    'StopRef': {
                        'Value': pce.stop.parent_id
                    },
                    'StopName': {
                        'Value': pce.stop.name,
                        'Language': 'DE'
                    },
                    'PassengerRelated': {
                        'Value': 'true'
                    }
                }
            # do not generate StopInformation at all, if there's no stop available
            # validation agains XSD fails in that case
            """else:
                pce_xml['StopInformation'] = {
                    'PassengerRelated': {
                        'Value': 'true'
                    }
                }"""
                
            # GPS position
            pce_xml['GNSS'] = {
                'GNSS_Point_Structure': {
                    'Longitude': {
                        'Degree': {
                            'Value': pce.longitude
                        },
                        'Direction': {
                            'Value': 0
                        }
                    },
                    'Latitude': {
                        'Degree': {
                            'Value': pce.latitude
                        },
                        'Direction': {
                            'Value': 0
                        }
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
                        'CountInfo': {
                            'DoorOpenTime': {
                                'Value': None
                            },
                            'DoorClosingTime': {
                                'Value': None
                            }
                        },
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
                        'CountingOperationState': 'normal',
                        'Count': list()
                    }

                    for object_class in object_classes:
                        cs: CountingSequence = next((cs for cs in pce.counting_sequences if cs.counting_area_id == counting_area_id and cs.door_id == door_id and cs.object_class == object_class), None)
                        if cs is not None:

                            counting_xml['CountInfo']['DoorOpenTime']['Value'] = cs.begin_timestamp.isoformat()
                            counting_xml['CountInfo']['DoorClosingTime']['Value'] = cs.end_timestamp.isoformat()

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
        xml = unparse({
            'PassengerCountingMessage': result
        }, pretty=True)

        return (operation_day, trip_id, vehicle_id), xml
    
    def _export(self, transformed_data: Dict[tuple, str], output_directory: str) -> None:   
        
        # write each dataset to a single file
        for k, x in transformed_data.items():

            formatted_date: str = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')

            operation_day: int = k[0]
            trip_id: int = k[1]
            vehicle_id: str = k[2]

            output_filename: str = os.path.join(
                output_directory, 
                f"{formatted_date}_O{operation_day}_T{trip_id}_{vehicle_id}.xml"
            )

            with open(output_filename, 'w') as output_file:
                output_file.write(x)