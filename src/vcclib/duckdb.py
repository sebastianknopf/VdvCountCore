import duckdb
import json
import logging
import os

from datetime import datetime
from typing import Any
from typing import Dict

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

    def get_primary_data_indicators(self) -> Dict[tuple, str]:
        stmt = self._load_sql_statement('select_primary_data_indicators')
    
    def _load_sql_statement(self, sql_filename: str, **arguments: Any) -> str:

        sql_filename = os.path.join('/etc/resources/sql', f"{sql_filename}.sql")
        with open(sql_filename, 'r', encoding='utf-8') as sql_file:
            sql_statement = sql_file.read()

        for key, value in arguments.items():
            sql_statement = sql_statement.replace(f"%%{key}%%", value)

        # log generated SQL statement in debugging mode
        if os.getenv('VCC_DEBUG', 'false').lower() == 'true' or os.getenv('VCC_DEBUG', 'false') == '1':
            logging.info(sql_statement)

        return sql_statement
    
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