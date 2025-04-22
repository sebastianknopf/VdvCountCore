import os
import shutil

from datetime import datetime

def directory_contains_files(directory: str) -> bool:
    with os.scandir(directory) as entries:
        return any(e.is_file() for e in entries)
    

def file_exists(directory: str, filename: str) -> bool:
    for entry in os.listdir(directory):
        if entry.lower() == filename.lower():
            if os.path.isfile(os.path.join(directory, entry)):
                return True
        
    return False

    
def archive_directory_files(directory: str, defective: bool = False) -> None:
    if directory_contains_files(directory):
        archive_directory = os.path.join(directory, 'Archive' if not defective else 'Defective', datetime.now().strftime('%Y%m%d%H%M%S'))
        os.makedirs(archive_directory)

        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.is_file():
                    s = entry.path
                    d = os.path.join(archive_directory, entry.name)

                    shutil.move(s, d)