import click
import logging
import os
import schedule
import time

from croniter import croniter
from datetime import datetime

from vcclib import database
from vccvdv452import.adapter.base import BaseAdapter
from vccvdv452import.adapter.default import DefaultAdapter
from vccvdv452import.adapter.vvs import VvsAdapter

def run():
    
    now = datetime.now().replace(second=0, microsecond=0)
    cron = os.getenv('VCC_MD_IMPORT_INTERVAL', '0 */1 * * *')

    if croniter.match(cron, now):
        _run_now()

def _run_now():
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
    _run_now()

    # run main method
    schedule.every(1).minutes.do(run)

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    cli()
