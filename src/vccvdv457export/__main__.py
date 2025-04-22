import click
import os
import time

from croniter import croniter
from datetime import datetime

def run():

    now = datetime.now()
    cron = os.getenv('VCC_VDV457_EXPORT_INTERVAL', '0 */1 * * *')

    if croniter.match(cron, now):
        print('Main VDV457 Export', flush=True)    

@click.group()
def cli():
    pass

@cli.command()
def main():

    while True:
        run()
        time.sleep(60)

if __name__ == '__main__':
    cli()
