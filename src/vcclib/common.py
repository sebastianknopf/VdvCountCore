import os

from datetime import datetime

def is_set(variable_name: str) -> bool:
    variable_value: str = os.getenv(variable_name, 'false').lower().strip()
    return variable_value == 'true' or variable_value == '1'

def is_debug() -> bool:
    return is_set('VCC_DEBUG')

def isoformattime(dt: datetime) -> str:
    iso: str = dt.strftime('%H:%M:%S%z')

    if '+' in iso:
        iso = iso[:-2] + ":" + iso[-2:]

    return iso