import click
import os
import time

from croniter import croniter
from datetime import datetime

def run():

    now = datetime.now()
    cron = os.getenv('VCC_VDV457_EXPORT_INTERVAL', '0 */1 * * *')

    print(cron, flush=True)
    if croniter.match(cron, now):
        _run_now()

def _run_now():
    print('Main VDV457 Export', flush=True)

@click.group()
def cli():
    pass

@cli.command()
def main():

    # run main method first time
    _run_now()

    while True:
        run()
        time.sleep(50)

if __name__ == '__main__':
    cli()
