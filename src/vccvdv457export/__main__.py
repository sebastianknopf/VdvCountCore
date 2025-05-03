import click
import logging
import os
import time

import vccvdv457export.adapter.s2 as s2
import vccvdv457export.adapter.s3 as s3

from croniter import croniter
from datetime import datetime

from vccvdv457export.adapter.base import BaseAdapter

def run():
    
    now = datetime.now().replace(second=0, microsecond=0)
    cron = os.getenv('VCC_VDV452_IMPORT_INTERVAL', '0 3 * * *')

    if croniter.match(cron, now):
        _run_now()

def _run_now():

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
            adapter.process('/data/input', '/data/vdv4572')
        except Exception as ex:
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
            adapter.process('/data/input', '/data/vdv4573')
        except Exception as ex:
            if os.getenv('VCC_DEBUG', '0') == '1':
                logging.exception(ex)
            else:
                logging.error(str(ex))   

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
