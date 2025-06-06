import duckdb
import json
import logging
import os

from datetime import datetime
from typing import Any
from typing import Dict
from typing import List

from .common import is_debug

class DuckDB:

    def __init__(self, data_directory: str, schema_filename: str):
        
        table_name = 'vccdata'

        with open(schema_filename, 'r', encoding='utf-8') as schema_file:
            json_schema = json.load(schema_file)

        ddb_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}.ddb"

        self._ddb = duckdb.connect(os.path.join(data_directory, ddb_name))    
        self._ddb.execute(self._json_schema_to_create_statement(table_name, json_schema))

        for filename in os.listdir(data_directory):
            if filename.endswith('.json'):
                logging.info(f"Loading file {filename} ...")
                self._ddb.execute(f"INSERT INTO {table_name} SELECT * FROM read_json_auto('{os.path.join(data_directory, filename)}')")

    def get_primary_indicators(self) -> Dict[tuple, str]:
        result = self._execute_sql_statement('select_primary_indicators')

        # log results in debugging mode
        if is_debug():
            logging.info(result)

        # transform result into dict
        primary_indicators = {
            (k1, k2, k3): v
            for k1, k2, k3, v in zip(
                result['operation_day'].to_list(), 
                result['trip_id'].to_list(), 
                result['vehicle_id'].to_list(),
                result['device_id'].to_list()
            )
        }

        return primary_indicators

    def get_secondary_device_ids(self, operation_day: int, trip_id: str, vehicle_id: str, primary_device_id: str) -> List[str]:
        result = self._execute_sql_statement(
            'select_secondary_device_ids', 
            operation_day=operation_day, 
            trip_id=trip_id,
            vehicle_id=vehicle_id,
            device_id=primary_device_id
        )

        # log results in debugging mode
        if is_debug():
            logging.info(result)

        return result["device_id"].to_list()
    
    def get_data(self, operation_day: int, trip_id: str, vehicle_id:str, device_id: str) -> List[dict]:
        result = self._execute_sql_statement(
            'select_data', 
            operation_day=operation_day, 
            trip_id=trip_id,
            vehicle_id=vehicle_id,
            device_id=device_id
        )

        # log results in debugging mode
        if is_debug():
            logging.info(result)

        # transform result into list
        return result.to_dicts()
    
    def get_trip_details(self, operation_day: int, trip_id: int, vehicle_id: str) -> List[dict]:
        result = self._execute_sql_statement(
            'select_trip_details',
            operation_day=operation_day,
            trip_id=trip_id,
            vehicle_id=vehicle_id
        )

        # log results in debugging mode
        if is_debug():
            logging.info(result)

        # transform result into list
        return result.to_dicts()

    def _execute_sql_statement(self, sql_filename: str, **arguments: Any) -> str:

        # load statement file from resources
        sql_filename = os.path.join('/etc/resources/sql', f"{sql_filename}.sql")
        with open(sql_filename, 'r', encoding='utf-8') as sql_file:
            sql_statement = sql_file.read()

        # log generated SQL statement in debugging mode
        if is_debug():
            logging.info(sql_statement)

        result = self._ddb.execute(sql_statement, tuple(arguments.values())).pl()

        return result
    
    def _json_schema_to_create_statement(self, table_name: str, json_schema: dict) -> str:
        properties = json_schema.get("properties", {})
        required_fields = json_schema.get("required", [])

        columns = []

        for name, definition in properties.items():
            duckdb_type = self._resolve_type(name, definition)
            nullability = "NOT NULL" if name in required_fields else ""
            
            columns.append(f"\"{name}\" {duckdb_type} {nullability}".strip())

        columns_sql = ",\n  ".join(columns)
        create_stmt = f"CREATE TABLE {table_name} (\n  {columns_sql}\n);"

        return create_stmt
    
    def _resolve_type(self, name: str, definition) -> str:
        type_mapping = {
            'string': 'TEXT',
            'integer': 'INTEGER',
            'number': 'DOUBLE',
            'boolean': 'BOOLEAN'
        }
        
        if isinstance(definition, list):
            definition = definition[0]

        json_type = definition.get("type")

        if isinstance(json_type, list) and len(json_type) > 0:
            json_type = json_type[0]

        if json_type == "array":
            items = definition.get("items", [])
            inner_type = self._resolve_type(name + "_item", items)
            return f"{inner_type}[]"

        elif json_type == "object":
            props = definition.get("properties", {})
            if not props:
                return "STRUCT()"
            struct_fields = []
            for subname, subdef in props.items():
                sub_type = self._resolve_type(subname, subdef)
                struct_fields.append(f"\"{subname}\" {sub_type}")
            return f"STRUCT({', '.join(struct_fields)})"

        else:
            if json_type == "string" and definition.get("format") == "date-time":
                return "TIMESTAMP"
            return type_mapping.get(json_type, "TEXT")

    def close(self):
        self._ddb.close()