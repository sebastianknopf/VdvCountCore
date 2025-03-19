import click
import logging
import os
import schedule
import time

from vcclib import database
from vccvdv452import.adapter.base import BaseAdapter
from vccvdv452import.adapter.default import DefaultAdapter
from vccvdv452import.adapter.vvs import VvsAdapter

def run():
    
    adapter: BaseAdapter = None

    adapter_type = os.getenv('VCC_VDV452_ADAPTER_TYPE', 'default')
    if adapter_type == 'default':
        adapter = DefaultAdapter()
    elif adapter_type == 'vvs':
        adapter = VvsAdapter()
    else:
        raise ValueError(f"Unknown adapter type {adapter_type}!")
    
    try:
        adapter.process('/data')
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

    # open DB connection
    database.init()

    # run main method first time
    run()

    # run main method as configured interval
    interval = int(os.getenv('VCC_VDV452_IMPORT_INTERVAL', 1440))
    schedule.every(interval).minutes.do(run)

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    cli()
