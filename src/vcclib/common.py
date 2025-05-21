import os

def is_debug() -> bool:
    return os.getenv('VCC_DEBUG', 'false').lower() == 'true' or os.getenv('VCC_DEBUG', 'false') == '1'