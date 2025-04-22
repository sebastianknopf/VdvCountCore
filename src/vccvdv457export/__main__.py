import click
import croniter
import os
import schedule
import time

from datetime import datetime

def run():

    now = datetime.now().replace(second=0, microsecond=0)
    cron = os.getenv('VCC_MD_IMPORT_INTERVAL', '0 */1 * * *')

    if croniter.match(cron, now):
        print('Main VDV457 Export', flush=True)

@click.group()
def cli():
    pass

@cli.command()
def main():

    # run main method first time
    run()

    # run main method
    schedule.every(1).minutes.do(run)

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    cli()
