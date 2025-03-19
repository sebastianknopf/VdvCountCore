import click
import os
import schedule
import time

def run():
    print('Main VDV457 Export', flush=True)

@click.group()
def cli():
    pass

@cli.command()
def main():

    # run main method first time
    run()

    # run main method as configured interval
    interval = int(os.getenv('VCC_VDV457_EXPORT_INTERVAL', 1440))
    schedule.every(interval).minutes.do(run)

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    cli()
