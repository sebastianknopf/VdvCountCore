import duckdb
import json
import os

class DuckDB:

    def __init__(self, data_directory: str, schema_filename: str):
        
        table_name = 'vccdata'

        with open(schema_filename, 'r', encoding='utf-8') as schema_file:
            json_schema = json.load(schema_file)

        self._ddb = duckdb.connect(os.path.join(data_directory, '.ddb'))    
        self._ddb.execute(self._json_schema_to_create_statement(json_schema))
        self._ddb.execute(f"INSERT INTO {table_name} SELECT * FROM json_load_auto('{os.path.join(data_directory, '*.json')}')")

    def _json_schema_to_create_statement(self, table_name, json_schema: str) -> str:
        return None

    def close(self):
        self._ddb.close()