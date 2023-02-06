import os
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from charlotte import charlotte
from opera import opera

pd.options.mode.chained_assignment = None


def main():
    # Remove data.jsonl file if it exists
    fp = "data.jsonl"
    if os.path.exists(fp):
        os.remove(fp)
        print(f"{fp} removed from directory.\n->Downloading gig data.")
    else:
        print(f"{fp} not in directory.\n->Downloading gig data.")

    # Use web crawlers to exctract gig data
    charlotte()

    # Get Opera House data
    df1 = opera()

    # Open data.jsonl file
    df2 = pd.read_json("data.jsonl", lines=True)

    # Combine DataFrames
    df = pd.concat([df1, df2])

    # Convert Event_Date to datetime
    df["Event_Date"] = pd.to_datetime(df["Event_Date"])

    # Sort Event_Date & Band columns
    df = df.sort_values(by=["Event_Date", "Band"])

    # Filter dates
    start_date = str(date.today())
    end_date = str(date.today() + timedelta(days=365))
    df = df.query("Event_Date > @start_date and Event_Date < @end_date")

    # Update text
    df["Band"] = df["Band"].str.title()
    df["Venue"] = df["Venue"].str.title().str.replace(", Sydney", "")

    # Create new Data column
    new_col = df["Event_Date"].dt.strftime("%d-%b-%-y (%a)")
    df.insert(1, "Date", new_col)

    # Create Path
    dir_path = str(Path.home() / "Desktop")

    # Save CSVs to Desktop
    gigs_table(dir_path, df)
    pretty_table(dir_path, df, start_date)


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
