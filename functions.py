import os
from typing import Set, Dict
import stat
import shutil

class MyClass:
    def __init__(self, dir1, dir2):
        self.dir1 = dir1
        self.dir2 = dir2

        self.deleted_files = []
        self.deleted_directories = []

    def walk_directory(self, directory: str, result_set: Set[str]) -> None:
        """Walk through a directory and store relative paths."""
        try:
            for cwd, dirs, files in os.walk(directory):
                for f in dirs + files:
                    path = os.path.relpath(os.path.join(cwd, f), directory)
                    path = path.replace('\\', '/')  # Normalize path separators
                    result_set.add(path)
        except OSError as e:
            print(f"Error accessing directory {directory}: {e}")

    def compare(self, dir1: str, dir2: str) -> Dict[str, Set[str]]:
        """Compare contents of two directories without pattern matching."""
        
        dir1_contents: Set[str] = set()  # To store files and directories from dir1
        dir2_contents: Set[str] = set()  # To store files and directories from dir2

        # Walk through both directories
        self.walk_directory(dir1, dir1_contents)
        self.walk_directory(dir2, dir2_contents)

        # Find common files and directories
        common: Set[str] = dir1_contents.intersection(dir2_contents)
        
        # Remove common files/directories from both sets
        dir1_contents.difference_update(common)
        dir2_contents.difference_update(common)

        comparasion_object: Dict[str, Set[str]] = {'only_dir1': dir1_contents, 'only_dir2': dir2_contents, 'common': common}

        return comparasion_object
        

    def purge(self, comparasion_object: Dict[str, Set[str]]) -> None:
        """Purge files and directories that exist only in the target directory (dir2)."""
        
        # Iterate through the files and directories present only in dir2
        for f2 in comparasion_object['only_dir2']:
            
            fullf2 = os.path.join(self.dir2, f2)  # Full path to the file/directory in dir2

            try:
                # Check if it's a file and handle deletion
                if os.path.isfile(fullf2):
                    print(f"Deleting file {fullf2}")
                    self.delete_file(fullf2)

                # Check if it's a directory and handle deletion
                elif os.path.isdir(fullf2):
                    print(f"Deleting directory {fullf2}")
                    self.delete_directory(fullf2)

            except Exception as e:
                print(f"Error purging {fullf2}: {e}")
                continue

    def delete_file(self, filepath: str) -> None:
        """Delete a file with permission handling and error logging."""
        try:
            # Attempt to remove the file
            os.remove(filepath)
        except PermissionError:
            # Handle permission error by changing file permissions
            os.chmod(filepath, stat.S_IWRITE)
            os.remove(filepath)
        except OSError as e:
            print(f"Error deleting file {filepath}: {e}")
            return
        
        self.deleted_files.append(filepath)

    def delete_directory(self, dirpath: str) -> None:
        """Delete a directory recursively and handle errors."""
        try:
            # Attempt to remove the directory and its contents
            shutil.rmtree(dirpath, ignore_errors=True)
        except shutil.Error as e:
            print(f"Error deleting directory {dirpath}: {e}")
            return
        
        self.deleted_directories.append(dirpath)

    def copy_file_from_source(self, filename: str) -> None:
        """Copy a file from the source directory to the target directory, creating directories as needed."""
        
        # Normalize the path to use forward slashes and split the filename
        rel_path = filename.replace('\\', '/').split('/')
        rel_dir = '/'.join(rel_path[:-1])
        filename = rel_path[-1]

        # Construct full paths for both source and destination directories
        dir1 = os.path.join(self.dir1, rel_dir)
        dir2 = os.path.join(self.dir2, rel_dir)

        try:
            # Ensure the destination directory exists, creating it if necessary
            if not os.path.exists(dir2):
                try:
                    os.makedirs(dir2)
                except OSError as e:
                    print(f"Error creating directory {dir2}: {e}")
                    return
            
            source_file = os.path.join(dir1, filename)

            # Copy the file
            try:
                shutil.copy2(source_file, dir2)
                print(f"Copied file {source_file} to {dir2}")
            except Exception as e:
                print(f"Error copying file {source_file}: {e}")
                return

        except Exception as e:
            print(f"Error copying file {filename}: {e}")
            return

    def create_directory_in_target(self, f1: str) -> None:
        """Create a directory in the target directory (dir2)."""
        to_make = os.path.join(self.dir2, f1)
        if not os.path.exists(to_make):
            try:
                os.makedirs(to_make)
                print(f"Created directory {to_make}")
            except OSError as e:
                print(f"Error creating directory {to_make}: {e}")
                return

    def checks_only_on_source(self, comparasion_object: Dict[str, Set[str]]):
        """Handle files and directories only present in the source directory (dir1)."""

        # Iterate through the files and directories present only in dir1
        for f1 in comparasion_object['only_dir1']:

            try:
                # Get the file or directory status
                st = os.stat(os.path.join(self.dir1, f1))
            except os.error:
                print(f"Error accessing {f1}")
                continue  

            # Check if it's a file
            if stat.S_ISREG(st.st_mode):
                self.copy_file_from_source(f1)

            # Check if it's a directory
            elif stat.S_ISDIR(st.st_mode):
                self.create_directory_in_target(f1)

    def sync(self) -> None:
        """Sync the contents of two directories."""
        
        # Compare the contents of both directories
        comparasion_object = self.compare(self.dir1, self.dir2)
        
        # Purge files and directories that exist only in dir 2
        self.purge(comparasion_object)

        # Adds files and directories only present in the source directory
        self.checks_only_on_source(comparasion_object)

source = 'tests/folder1'
replica = 'tests/folder2'

# Check if the source directory exists
if not os.path.exists(source):
    print(f"Directory {source} does not exist.")
    exit(1)

syncronizer = MyClass(source, replica)
syncronizer.sync()