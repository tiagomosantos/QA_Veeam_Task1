"""
This module contains the DirectorySynchronizer class, which is used to synchronize two directories
"""

import hashlib
import logging
import shutil
import stat
import time
from pathlib import Path
from typing import Dict, Set


class DirectorySynchronizer:
    """Class to synchronize two directories periodically."""

    def __init__(
        self, dir1: str, dir2: str, sync_interval: int, loggers: tuple
    ) -> None:
        self.dir1 = Path(dir1)
        self.dir2 = Path(dir2)
        self.sync_interval = sync_interval

        # Initialize the logger inside the class
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

        # Create handlers
        info_log = loggers[0]
        error_log = loggers[1]
        info_handler = logging.FileHandler(info_log)
        error_handler = logging.FileHandler(error_log)

        # Set levels for handlers
        info_handler.setLevel(logging.INFO)
        error_handler.setLevel(logging.ERROR)

        # Create formatters and add them to handlers
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        info_handler.setFormatter(formatter)
        error_handler.setFormatter(formatter)

        # Add handlers to the logger
        self.logger.addHandler(info_handler)
        self.logger.addHandler(error_handler)

    def walk_directory(self, directory: Path, result_set: Set[Path]) -> None:
        """Walk through a directory and store relative paths."""
        try:
            for path in directory.rglob("*"):
                relative_path = path.relative_to(directory)
                result_set.add(relative_path)
        except OSError as e:
            self.logger.error("Error accessing directory %s: %s", directory, e)

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

        comparasion_object: Dict[str, Set[Path]] = {
            "only_dir1": dir1_contents,
            "only_dir2": dir2_contents,
            "common": common,
        }

        return comparasion_object

    def purge(self, comparasion_object: Dict[str, Set[Path]]) -> None:
        """Purge files and directories that exist only in the target directory (dir2)."""
        # Iterate through the files and directories present only in dir2
        for f2 in comparasion_object["only_dir2"]:
            fullf2 = self.dir2 / f2  # Full path to the file/directory in dir2
            try:
                if fullf2.is_file():
                    self.logger.info("Deleting file %s", fullf2)
                    self.delete_file(fullf2)
                elif fullf2.is_dir():
                    self.logger.info("Deleting directory %s", fullf2)
                    self.delete_directory(fullf2)
            except (PermissionError, OSError) as e:
                self.logger.error("Error purging %s: %s", fullf2, e)
                continue

    def delete_file(self, filepath: Path) -> None:
        """Delete a file with permission handling and error logging."""
        try:
            filepath.unlink()
        except PermissionError:
            filepath.chmod(stat.S_IWRITE)
            filepath.unlink()
            return
        except OSError as e:
            self.logger.error("Error deleting file %s: %s", filepath, e)
            return

    def delete_directory(self, dirpath: Path) -> None:
        """Delete a directory recursively and handle errors."""
        try:
            shutil.rmtree(dirpath, ignore_errors=True)
            return
        except shutil.Error as e:
            self.logger.error("Error deleting directory %s: %s", dirpath, e)
            return

    def copy_file_from_source(self, filename: Path) -> None:
        """Copy a file from the source directory to the target directory,
        creating directories as needed."""

        source_file = self.dir1 / filename
        destination_dir = self.dir2 / filename.parent

        try:
            destination_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, self.dir2 / filename)
            self.logger.info("Copied file %s to %s", source_file, self.dir2 / filename)
            return
        except (PermissionError, OSError) as e:
            self.logger.error("Error copying file %s: %s", source_file, e)
            return

    def create_directory_in_target(self, f1: Path) -> None:
        """Create a directory in the target directory (dir2)."""
        to_make = self.dir2 / f1
        try:
            to_make.mkdir(parents=True, exist_ok=True)
            self.logger.info("Created directory %s", to_make)
            return
        except OSError as e:
            self.logger.error("Error creating directory %s: %s", to_make, e)
            return

    def checks_only_on_source(self, comparasion_object: Dict[str, Set[Path]]) -> None:
        """Handle files and directories only present in the source directory (dir1)."""

        for f1 in comparasion_object["only_dir1"]:
            fullf1 = self.dir1 / f1
            try:
                if fullf1.is_file():
                    self.copy_file_from_source(f1)
                elif fullf1.is_dir():
                    self.create_directory_in_target(f1)
            except (PermissionError, OSError) as e:
                self.logger.error("Error accessing %s: %s", f1, e)
                continue

    def calculate_sha256(self, file_path: Path) -> str:
        """Calculate the SHA-256 hash of a file."""
        sha256 = hashlib.sha256()

        try:
            with file_path.open("rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256.update(byte_block)
        except (PermissionError, OSError) as e:
            self.logger.error("Error calculating SHA-256 hash for %s: %s", file_path, e)
            return ""

        return sha256.hexdigest()

    def update_common_files(self, comparasion_object: Dict[str, Set[Path]]) -> None:
        """Update common files between the two directories."""
        common_files = comparasion_object["common"]

        for f in common_files:
            file1 = self.dir1 / f
            file2 = self.dir2 / f

            if file1.is_file() and file2.is_file():
                hash1 = self.calculate_sha256(file1)
                hash2 = self.calculate_sha256(file2)

                if hash1 != hash2 and hash1 != "" and hash2 != "":
                    try:
                        shutil.copy2(file1, file2)
                        self.logger.info("Updated file %s", file2)
                    except (PermissionError, OSError) as e:
                        self.logger.error("Error updating file %s: %s", file2, e)

    def sync_directories(self) -> None:
        """Sync the contents of two directories periodically."""
        while True:
            comparasion_object = self.compare(self.dir1, self.dir2)
            self.purge(comparasion_object)
            self.checks_only_on_source(comparasion_object)
            self.update_common_files(comparasion_object)
            time.sleep(
                self.sync_interval
            )  # Wait for the defined interval before the next synchronization
