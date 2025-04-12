import os
import shutil

from datetime import datetime

def directory_contains_files(directory: str) -> bool:
    with os.scandir(directory) as entries:
        return any(e.is_file() for e in entries)
    
def archive_directory_files(directory: str) -> None:
    if directory_contains_files(directory):
        archive_directory = os.path.join(directory, 'Archive', datetime.now().strftime('%Y%m%d%H%M%S'))
        os.makedirs(archive_directory)

        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.is_file():
                    s = entry.path
                    d = os.path.join(archive_directory, entry.name)

                    shutil.move(s, d)