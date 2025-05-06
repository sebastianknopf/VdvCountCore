import click
import logging
import os
import time

import vccvdv457export.adapter.s2.default as s2
import vccvdv457export.adapter.s3.default as s3

from croniter import croniter
from datetime import datetime

from vcclib.duckdb import DuckDB
from vcclib.filesystem import directory_contains_files
from vcclib.filesystem import stage_directory_files
from vcclib.filesystem import archive_directory_files
from vccvdv457export.adapter.base import BaseAdapter

def run():
    
    now = datetime.now().replace(second=0, microsecond=0)
    cron = os.getenv('VCC_VDV457_EXPORT_INTERVAL', '0 3 * * *')

    if croniter.match(cron, now):
        _run_now()

def _run_now():

    # set local varibales
    input_directory = '/data/input'
    stage_directory = '/data/stage'

    schema_filename = '/app/resources/schema.json'

    # check if input directory contains files at all...
    if not directory_contains_files(input_directory):
        logging.info(f"Input directory {input_directory} is empty")
        return
    else:
        # take files into staging directory in order to avoid archiving files which were added after starting a converter
        # remember: the converter may run several minutes!
        logging.info(f"Staging files in input directory {input_directory} to stage directory {stage_directory}  ...")
        stage_directory_files(input_directory, stage_directory)

    # initialize DuckDB instance
    ddb = DuckDB(stage_directory, schema_filename)

    # check whether all converters were running fine...
    # set to true at first, in case there's no converter enabled at all to avoid unneccessary 
    # archive folders
    any_converter_failed = False

    # instantiate and run VDV457-2 conversion
    vdv457_convert_2 = os.getenv('VCC_VDV457_EXPORT_CONVERT_2', 'false').lower()
    if vdv457_convert_2 == 'true':   

        adapter: BaseAdapter = None

        adapter_type = os.getenv('VCC_VDV457_EXPORT_ADAPTER_TYPE_2', 'default')
        if adapter_type == 'default':
            adapter = s2.DefaultAdapter()
        else:
            raise ValueError(f"Unknown VDV457-2 adapter type {adapter_type}!")
        
        try:
            adapter.process(ddb, '/data/vdv4572')
        except Exception as ex:
            any_converter_failed = True
            if os.getenv('VCC_DEBUG', '0') == '1':
                logging.exception(ex)
            else:
                logging.error(str(ex))

    # instantiate and run VDV457-3 conversion
    vdv457_convert_3 = os.getenv('VCC_VDV457_EXPORT_CONVERT_3', 'false').lower()
    if vdv457_convert_3 == 'true':

        adapter: BaseAdapter = None

        adapter_type = os.getenv('VCC_VDV457_EXPORT_ADAPTER_TYPE_3', 'default')
        if adapter_type == 'default':
            adapter = s3.DefaultAdapter()
        else:
            raise ValueError(f"Unknown VDV457-3 adapter type {adapter_type}!")

        try:
            adapter.process(ddb, '/data/vdv4573')
        except Exception as ex:
            any_converter_failed = True
            if os.getenv('VCC_DEBUG', '0') == '1':
                logging.exception(ex)
            else:
                logging.error(str(ex))  

    # close DuckDB instance with data loaded
    ddb.close()

    # if all converters ran without error, archive input files; otherwise put them in an error folder
    # archive shall be created in input directory, so pass this as destination variable
    logging.info(f"Archiving files in input directory {stage_directory} ...")
    archive_directory_files(stage_directory, input_directory, any_converter_failed)

@click.group()
def cli():
    pass

@cli.command()
def main():

    # set logging default configuration
    logging.basicConfig(format="[%(levelname)s] %(asctime)s %(message)s", level=logging.INFO)

    # run export first time at startup
    _run_now()

    while True:
        run()
        time.sleep(60)

if __name__ == '__main__':
    cli()
