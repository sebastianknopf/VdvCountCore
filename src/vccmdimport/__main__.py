import click
import os
import schedule
import time

def run():
    print('Main MD Import', flush=True)

@click.group()
def cli():
    pass

@cli.command()
def main():

    # run main method first time
    run()

    # run main method as configured interval
    interval = int(os.getenv('VCC_MD_IMPORT_INTERVAL', 1440))
    schedule.every(interval).minutes.do(run)

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    cli()
