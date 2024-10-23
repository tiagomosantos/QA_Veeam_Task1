from pathlib import Path
from typing import Set, Dict
import stat
import shutil
import hashlib
import time
import logging
import argparse

class DirectorySynchronizer:
    def __init__(self, dir1: str, dir2: str, sync_interval: int, info_log: str, error_log: str) -> None:
        self.dir1 = Path(dir1)
        self.dir2 = Path(dir2)
        self.sync_interval = sync_interval  

        # Initialize the logger inside the class
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

        # Create handlers
        info_handler = logging.FileHandler(info_log)
        error_handler = logging.FileHandler(error_log)

        # Set levels for handlers
        info_handler.setLevel(logging.INFO)
        error_handler.setLevel(logging.ERROR)

        # Create formatters and add them to handlers
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        info_handler.setFormatter(formatter)
        error_handler.setFormatter(formatter)

        # Add handlers to the logger
        self.logger.addHandler(info_handler)
        self.logger.addHandler(error_handler)

    def walk_directory(self, directory: Path, result_set: Set[Path]) -> None:
        """Walk through a directory and store relative paths."""
        try:
            for path in directory.rglob('*'):
                relative_path = path.relative_to(directory)
                result_set.add(relative_path)
        except OSError as e:
            self.logger.error(f"Error accessing directory {directory}: {e}")

    def compare(self, dir1: Path, dir2: Path) -> Dict[str, Set[Path]]:
        """Compare contents of two directories without pattern matching."""
        
        dir1_contents: Set[Path] = set()  # To store files and directories from dir1
        dir2_contents: Set[Path] = set()  # To store files and directories from dir2

        # Walk through both directories
        self.walk_directory(dir1, dir1_contents)
        self.walk_directory(dir2, dir2_contents)

        # Find common files and directories
        common: Set[Path] = dir1_contents.intersection(dir2_contents)
        
        # Remove common files/directories from both sets
        dir1_contents.difference_update(common)
        dir2_contents.difference_update(common)

        comparasion_object: Dict[str, Set[Path]] = {'only_dir1': dir1_contents, 'only_dir2': dir2_contents, 'common': common}

        return comparasion_object
        

    def purge(self, comparasion_object: Dict[str, Set[Path]]) -> None:
        """Purge files and directories that exist only in the target directory (dir2)."""
        
        # Iterate through the files and directories present only in dir2
        for f2 in comparasion_object['only_dir2']:
            fullf2 = self.dir2 / f2  # Full path to the file/directory in dir2

            try:
                if fullf2.is_file():
                    self.logger.info(f"Deleting file {fullf2}")
                    self.delete_file(fullf2)
                elif fullf2.is_dir():
                    self.logger.info(f"Deleting directory {fullf2}")
                    self.delete_directory(fullf2)
            except Exception as e:
                self.logger.error(f"Error purging {fullf2}: {e}")
                continue

    def delete_file(self, filepath: Path) -> None:
        """Delete a file with permission handling and error logging."""
        try:
            filepath.unlink()
        except PermissionError:
            filepath.chmod(stat.S_IWRITE)
            filepath.unlink()
        except OSError as e:
            self.logger.error(f"Error deleting file {filepath}: {e}")
            return
        
    def delete_directory(self, dirpath: Path) -> None:
        """Delete a directory recursively and handle errors."""
        try:
            shutil.rmtree(dirpath, ignore_errors=True)
        except shutil.Error as e:
            self.logger.error(f"Error deleting directory {dirpath}: {e}")
            return
        
    def copy_file_from_source(self, filename: Path) -> None:
        """Copy a file from the source directory to the target directory, creating directories as needed."""
        
        source_file = self.dir1 / filename
        destination_dir = self.dir2 / filename.parent
        
        try:
            destination_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, self.dir2 / filename)
            self.logger.info(f"Copied file {source_file} to {self.dir2 / filename}")
        except Exception as e:
            self.logger.error(f"Error copying file {source_file}: {e}")
            return

    def create_directory_in_target(self, f1: Path) -> None:
        """Create a directory in the target directory (dir2)."""
        to_make = self.dir2 / f1
        try:
            to_make.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Created directory {to_make}")
        except OSError as e:
            self.logger.error(f"Error creating directory {to_make}: {e}")
            return

    def checks_only_on_source(self, comparasion_object: Dict[str, Set[Path]]) -> None:
        """Handle files and directories only present in the source directory (dir1)."""

        for f1 in comparasion_object['only_dir1']:
            fullf1 = self.dir1 / f1
            try:
                if fullf1.is_file():
                    self.copy_file_from_source(f1)
                elif fullf1.is_dir():
                    self.create_directory_in_target(f1)
            except Exception as e:
                self.logger.error(f"Error accessing {f1}: {e}")
                continue  

    def calculate_sha256(self, file_path: Path) -> str:
        """Calculate the SHA-256 hash of a file."""
        sha256 = hashlib.sha256()
    
        try:
            with file_path.open("rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256.update(byte_block)
        except Exception as e:
            self.logger.error(f"Error calculating SHA-256 hash for {file_path}: {e}")
            return None
        
        return sha256.hexdigest()

    def update_common_files(self, comparasion_object: Dict[str, Set[Path]]) -> None:
        """Update common files between the two directories."""
        common_files = comparasion_object['common']

        for f in common_files:
            file1 = self.dir1 / f
            file2 = self.dir2 / f

            if file1.is_file() and file2.is_file():
                hash1 = self.calculate_sha256(file1)
                hash2 = self.calculate_sha256(file2)

                if hash1 and hash2 and hash1 != hash2:
                    try:
                        shutil.copy2(file1, file2)
                        self.logger.info(f"Updated file {file2}")
                    except Exception as e:
                        self.logger.error(f"Error updating file {file2}: {e}")

    def sync_directories(self) -> None:
        """Sync the contents of two directories periodically."""
        while True:
            comparasion_object = self.compare(self.dir1, self.dir2)
            self.purge(comparasion_object)
            self.checks_only_on_source(comparasion_object)
            self.update_common_files(comparasion_object)
            time.sleep(self.sync_interval)  # Wait for the defined interval before the next synchronization

source = 'tests/folder1'
replica = 'tests/folder2'
sync_interval = 60  # Sync every 60 seconds
info_log_file = 'info.log'
error_log_file = 'error.log'




def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Synchronize two directories periodically.")
    
    parser.add_argument("source", type=str, help="Source folder path")
    parser.add_argument("replica", type=str, help="Replica folder path")
    
    # Add optional arguments with default values
    parser.add_argument("--interval", type=int, default=30, help="Synchronization interval in seconds (default: 30)")
    parser.add_argument("--info_log", type=str, default="info.log", help="Path to log file for info messages (default: 'info.log')")
    parser.add_argument("--error_log", type=str, default="error.log", help="Path to log file for error messages (default: 'error.log')")
    
    args = parser.parse_args()
    
    # Check if the source folder exist
    if not Path(source).exists():
        print(f"Source directory {source} does not exist.")
    else:
        # Initialize the synchronizer with the arguments
        synchronizer = DirectorySynchronizer(
            dir1=args.source, 
            dir2=args.replica, 
            sync_interval=args.interval, 
            info_log=args.info_log, 
            error_log=args.error_log
        )
        
        # Start the synchronization process
        synchronizer.sync_directories()

if __name__ == "__main__":
    main()