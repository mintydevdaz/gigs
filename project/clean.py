import os
import pandas as pd
from pathlib import Path
from datetime import date, timedelta


# TODO: DROP DUPES


def main():
    # Get filepath & list of filepath objects
    fp = str(Path.home() / "Desktop" / "csv_files")
    folder = os.listdir(fp)

    # Create DataFrame
    df = open_table(fp, folder)

    # Sort by Date
    df = sort_table(df)

    # Filter by Date & State
    df = filter_table(df)

    # Create 'Date' column
    df = create_date_column(df)

    # Prepare two CSV files for emailing
    gigs_table(fp, df)
    pretty_table(fp, df)


def open_table(file_path: str, folder: list[str]) -> pd.DataFrame:
    """Combines all CSV files located in folder path. Ignores DS_Store file.

    Args:
        file_path (str): Folder on Desktop
        folder (list[str]): List of files in folder

    Returns:
        pd.DataFrame: DataFrame containing list of all gigs
    """
    return pd.concat(
        [
            pd.read_csv(f"{file_path}/{file}")
            for file in folder
            if file.endswith(".csv")
        ],
        ignore_index=True,
    )


def sort_table(df: pd.DataFrame) -> pd.DataFrame:
    """Sorts DataFrame by ascending date then alphabetical order.
    Converts 'Event_Date' column to Datetime object then sorts values.

    Args:
        df (pd.DataFrame): DataFrame combined with all CSV files.

    Returns:
        pd.DataFrame: Sorted DataFrame
    """
    df["Event_Date"] = pd.to_datetime(df["Event_Date"], dayfirst=True)
    df = df.sort_values(by=["Event_Date", "Event"])
    return df


def filter_table(df: pd.DataFrame) -> pd.DataFrame:
    start_date = str(date.today())
    end_date = str(date.today() + timedelta(days=365))
    df = df.query("Event_Date > @start_date and Event_Date < @end_date")
    df = df[df.State == "NSW"]
    return df


def create_date_column(df: pd.DataFrame) -> pd.DataFrame:
    """Prepares and inserts new 'Date' column for presentation purposes.

    Args:
        df (pd.DataFrame): Pandas DataFrame

    Returns:
        pd.DataFrame: DataFrame with new Data column added
    """
    new_col = df["Event_Date"].dt.strftime("%d-%b-%-y (%a)")
    df.insert(1, "Date", new_col)
    return df


def gigs_table(directory_path: str, df: pd.DataFrame):
    """Saves a CSV file of all gigs to the Desktop path.

    Args:
        directory_path (str): Hard-coded path to folder on Desktop
        df (pd.DataFrame): DataFrame containing all gigs

    Returns:
        csv: CSV file
    """
    df = df.drop(["Event_Date", "State"], axis="columns")
    path = f"{directory_path}/gigs.csv"
    df.to_csv(path, index=False)
    print(f"Saved to {path}")


def pretty_table(directory_path: str, df: pd.DataFrame):
    """Saves a CSV file of gigs for 30 days from today.

    Args:
        directory_path (str): Hard-coded path to folder on Desktop
        df (pd.DataFrame): DataFrame containing all gigs

    Returns:
        csv: CSV file
    """
    start_date = str(date.today())
    end_date = str(date.today() + timedelta(days=30))
    df = df.query("Event_Date > @start_date and Event_Date < @end_date")
    df = df.drop("Event_Date", axis="columns")
    path = f"{directory_path}/pretty_table.csv"
    df.to_csv(path, index=False)
    print(f"Saved to {path}")


if __name__ == "__main__":
    main()
