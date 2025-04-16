import csv
import logging
import os

from vcclib import database
from vcclib.model import MasterDataVehicle
from vcclib.model import MasterDataObjectClass
from vcclib.filesystem import directory_contains_files
from vccmdimport.adapter.base import BaseAdapter

class CsvAdapter(BaseAdapter):

    def __init__(self) -> None:
        pass

    def process(self, input_directory: str) -> None:
        # verify input directory and files present
        if not self._verify(input_directory):
            return
        
        # define processing variables
        batch_size = 2500

        # clear database before insert
        logging.info('Clearing database ...')
        
        MasterDataVehicle.deleteMany(where=None)
        MasterDataObjectClass.deleteMany(where=None)

        transaction = database.connection().transaction()
        transaction_count = 0

        # load network data ...
        logging.info('Loading vehicles ...')

        vehicle_data = self._internal_read_csv_file(input_directory, 'vehicles.csv')
        for i, record in enumerate(vehicle_data):
            try:
                MasterDataVehicle(
                    name=record['name'],
                    num_doors=int(record['num_doors']),
                    connection=transaction
                )

                if transaction_count >= batch_size or i >= len(vehicle_data) - 1:
                    transaction.commit()

                    transaction = database.connection().transaction()
                    transaction_count = 0

            except Exception as ex:
                transaction.rollback()
                transaction_count = 0

                if not i >= len(vehicle_data):
                    transaction = database.connection().transaction()

                raise ex
            
        # load network data ...
        logging.info('Loading object classes ...')

        object_class_data = self._internal_read_csv_file(input_directory, 'object_classes.csv')
        for i, record in enumerate(object_class_data):
            try:
                MasterDataObjectClass(
                    name=record['name'],
                    description=int(record['description']),
                    connection=transaction
                )

                if transaction_count >= batch_size or i >= len(object_class_data) - 1:
                    transaction.commit()

                    transaction = database.connection().transaction()
                    transaction_count = 0

            except Exception as ex:
                transaction.rollback()
                transaction_count = 0

                if not i >= len(object_class_data):
                    transaction = database.connection().transaction()

                raise ex

    def _verify(self, input_directory:str) -> bool:
        logging.info(f"Verifying files in input directory {input_directory} ...")

        if not os.path.isdir(input_directory):
            raise ValueError(f"Input directory {input_directory} is no directory!")
        
        if not directory_contains_files(input_directory):
            logging.info(f"Input directory {input_directory} is empty!")
            return False

        csv_vehicles_filename = os.path.join(input_directory, 'vehicles.csv')
        if not os.path.exists(csv_vehicles_filename) or not os.path.isfile(csv_vehicles_filename):
            raise FileNotFoundError(f"Required file {csv_vehicles_filename} not found")
        
        csv_object_classes_filename = os.path.join(input_directory, 'object_classes.csv')
        if not os.path.exists(csv_object_classes_filename) or not os.path.isfile(csv_object_classes_filename):
            raise FileNotFoundError(f"Required file {csv_object_classes_filename} not found")

    def _internal_read_csv_file(self, input_directory: str, csv_filename: str) -> dict:
        for entry in os.listdir(input_directory):
            if entry.lower() == csv_filename.lower():
                csv_filename = entry
                break
        
        csv_filename = os.path.join(input_directory, csv_filename)

        if not os.path.exists(csv_filename) or not os.path.isfile(csv_filename):
            raise FileNotFoundError(f"File {csv_filename} not found!")
        
        csv_data = list()
        with open(csv_filename, 'r', encoding='utf-8') as csv_file:
            csv_reader = csv.DictReader(csv_file, delimiter=';')
            csv_data = [line for line in csv_reader]

        return csv_data