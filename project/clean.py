import os
import pandas as pd
from pathlib import Path
from datetime import date, timedelta


def main():
    # Create path to folder
    fp = str(Path.home() / "Desktop" / "csv_files")
    folder = os.listdir(fp)

    # Open files in pd.DataFrame
    df = pd.concat([pd.read_csv(f"{fp}/{csv}") for csv in folder], ignore_index=True)

    # ! Apply filtering
    # Filter NSW col
    df = df[df.State == "NSW"]

    # Sort by date
    df['Event_Date'] = pd.to_datetime(df['Event_Date'], dayfirst=True)
    df = df.sort_values(by=['Event_Date', "Event"])

    # Filter dates
    start_date = str(date.today())
    end_date = str(date.today() + timedelta(days=365))
    df = df.query("Event_Date > @start_date and Event_Date < @end_date")

    # Create new Date col
    new_col = df["Event_Date"].dt.strftime("%d-%b-%-y (%a)")
    df.insert(1, "Date", new_col)

    # Save CSV files
    gigs_table(fp, df)
    pretty_table(fp, df, start_date)


def gigs_table(directory_path: str, df: pd.DataFrame):
    f = "gigs.csv"
    path = f"{directory_path}/{f}"
    df = df.drop("Event_Date", axis="columns")
    df.to_csv(path, index=False)
    print(f"Saved to {path}")


def pretty_table(directory_path: str, df: pd.DataFrame, start_date: str):
    f = "pretty_table.csv"
    path = f"{directory_path}/{f}"
    end_date = str(date.today() + timedelta(days=30))
    df = df.query("Event_Date > @start_date and Event_Date < @end_date")
    df = df.drop("Event_Date", axis="columns")
    df.to_csv(path, index=False)
    print(f"Saved to {path}")


if __name__ == "__main__":
    main()
