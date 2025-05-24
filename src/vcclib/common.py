import os

from datetime import datetime

def is_debug() -> bool:
    return os.getenv('VCC_DEBUG', 'false').lower() == 'true' or os.getenv('VCC_DEBUG', 'false') == '1'

def isoformattime(dt: datetime) -> str:
    iso: str = dt.strftime('%H:%M:%S%z')

    if '+' in iso:
        iso = iso[:-2] + ":" + iso[:-2]

    return iso