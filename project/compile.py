import os
import sys
from pathlib import Path

from opera import opera
from spider import spider
from ticketek import ticketek


def main():
    try:
        folder = "csv_files"
        parent_dir = str(Path.home() / "Desktop/")
        path = os.path.join(parent_dir, folder)
        os.mkdir(path)
        print(f"-> New folder created at: {path}")
    except OSError as err:
        sys.exit(f"-> Operation aborted: ***{err}***")

    print("-> Fetching gig data...")
    opera()
    ticketek()
    spider()

    # List directory files
    print("-> New csv files succesfully created:")
    for i, csv in enumerate(os.listdir(path), start=1):
        print(f"{i}. {csv}")


if __name__ == "__main__":
    main()
