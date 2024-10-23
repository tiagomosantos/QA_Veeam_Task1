""" 
This script synchronizes two directories periodically. 
It compares the contents of two directories and performs the following actions:
1. Purge files and directories that exist only in the target directory.
2. Copy files and directories that exist only in the source directory to the target directory.
3. Update common files between the two directories.
"""

import argparse
from pathlib import Path
from components.synchronizer import DirectorySynchronizer


def main():
    """Main function to parse arguments and start the synchronization process."""
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Synchronize two directories periodically."
    )

    parser.add_argument("source", type=str, help="Source folder path")
    parser.add_argument("replica", type=str, help="Replica folder path")

    # Add optional arguments with default values
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Synchronization interval in seconds (default: 30)",
    )
    parser.add_argument(
        "--info_log",
        type=str,
        default="info.log",
        help="Path to log file for info messages (default: 'info.log')",
    )
    parser.add_argument(
        "--error_log",
        type=str,
        default="error.log",
        help="Path to log file for error messages (default: 'error.log')",
    )

    args = parser.parse_args()

    loggers = (args.info_log, args.error_log)

    # Check if the source folder exist
    if not Path(args.source).exists():
        print(f"Source directory {args.source} does not exist.")
    else:
        # Initialize the synchronizer with the arguments
        synchronizer = DirectorySynchronizer(
            dir1=args.source,
            dir2=args.replica,
            sync_interval=args.interval,
            loggers=loggers,
        )

        # Start the synchronization process
        synchronizer.sync_directories()


if __name__ == "__main__":
    main()
