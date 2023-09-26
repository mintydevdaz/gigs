import datetime
import logging
import os
from datetime import date, timedelta
from glob import glob
from pathlib import Path

import pandas as pd
import polars as pl
from CONSTANTS import SYDNEY_SUBURBS
from pretty_html_table import build_table
from utils import logger, save_path, timer


# ! 18-Sep-23 ~ Removed prices until I figure out how to scrape all of them


def create_file_list(omit_files: tuple[str, ...]) -> list[str]:
    """
    Creates a list of file paths to JSON files, excluding those specified in
    `omit_files`.

    Args:
        omit_files (tuple[str, ...]): A tuple of file extensions to omit from the file
        list.

    Returns:
        list[str]: A list of file paths to JSON files, excluding the specified
        `omit_files`.

    Example:
        ```python
        omit = (".txt", ".csv")

        file_list = create_file_list(omit)
        print(file_list)
        ```
    """
    data_filenames = glob(f"{str(Path.cwd() / 'data')}/*.json")
    return [f for f in data_filenames if not f.endswith(omit_files)]


def combine_tables(json_list: list[str]) -> pl.DataFrame:
    """
    Combines multiple tables from JSON files into a single DataFrame.

    Args:
        json_list (list[str]): A list of file paths to JSON files.

    Returns:
        pl.DataFrame: The concatenated DataFrame.

    Example:
        ```python
        json_files = [
            "/path/to/file1.json",
            "/path/to/file2.json",
            "/path/to/file3.json"
        ]

        combined_df = combine_tables(json_files)
        print(combined_df)
        ```
    """
    df_list = []
    for f in json_list:
        df = pl.read_json(f)
        df_list.append(df)
    return pl.concat(df_list)


def apply_formats(df: pl.DataFrame) -> pl.DataFrame:
    df = df.with_columns(
        pl.col(["title", "venue"]).str.to_lowercase(),
        pl.col("suburb").str.to_titlecase(),
    )
    return df


def add_columns(df: pl.DataFrame) -> pl.DataFrame:
    state = "NSW"
    state_column = "in_nsw"
    city_column = "in_sydney"

    df = df.with_columns((pl.col("state") == state.upper()).alias(state_column))
    df = df.with_columns(pl.col("suburb").is_in(SYDNEY_SUBURBS).alias(city_column))

    df = df.with_columns(pl.col("event_date").str.strptime(pl.Date, format="%d %b %Y"))
    df = df.with_columns(pl.col("event_date").dt.strftime("%d-%b-%y, %a").alias("Date"))

    df = df.with_columns(
        pl.col("price").map_elements(
            lambda price: f"${price:.2f}" if price != 0 else "-",  # type: ignore
            return_dtype=pl.Utf8,
        )
    )

    return df


def create_date_filters() -> tuple[datetime.date, ...]:
    today = date.today()
    end_month = today + timedelta(days=30)
    end_year = today + timedelta(days=365)
    return today, end_month, end_year


def apply_filter(
    df: pl.DataFrame, today: datetime.date, end_year: datetime.date
) -> pl.DataFrame:
    state_column = "in_nsw"
    city_column = "in_sydney"
    date_column = "event_date"

    df = df.filter(pl.col(state_column) & pl.col(city_column))
    df = df.filter(pl.col(date_column).is_between(today, end_year))

    return df


def apply_sort(df: pl.DataFrame) -> pl.DataFrame:
    return df.lazy().sort("event_date", descending=False).collect()


def remove_duplicate_rows(df: pl.DataFrame) -> pl.DataFrame:
    df = df.unique(subset=["title"], maintain_order=True)
    return df.unique(subset=["title", "venue"], maintain_order=True)


def build_month_table(
    df: pl.DataFrame, date_column: str, today: datetime.date, end_month: datetime.date
) -> pl.DataFrame:
    df = (
        df.select(
            pl.all(),
            pl.format("<a href={} target=_blank>{}</a>", pl.col("url"), "title").alias(
                "Event"
            ),
        )
        .filter(pl.col(date_column).is_between(today, end_month))
        .select(
            pl.col("Date"),
            pl.col("Event"),
            # pl.col("price").alias("Price"),
            pl.col("genre").alias("Genre"),
            pl.col("suburb").alias("Suburb"),
            pl.col("venue").alias("Venue"),
        )
    )
    return df


def replace_text_values(table: str) -> str:
    return (
        table.replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&amp;", "&")
        .replace("_blank", "'_blank'")
        .replace("\\", "'")
    )


def build_html_table(df: pd.DataFrame) -> str:
    raw_table = build_table(
        df,
        "yellow_light",
        font_family="Helvetica, sans-serif",
        text_align="left",
        width_dict=[
            "105px",
            "auto",
            "auto",
            "auto",
            "auto",
        ],
        padding="5px",
    )
    return replace_text_values(raw_table)


def save_to_text(
    df: pl.DataFrame, date_column: str, today: datetime.date, end_month: datetime.date
):
    month_table = build_month_table(df, "event_date", today, end_month)
    month_table.write_csv(file=save_path("gigs/data_files", "month_table.csv"))
    month_csv = pd.read_csv(save_path("gigs/data_files", "month_table.csv"))
    html_table = build_html_table(month_csv)
    fp = save_path("gigs/data_files", "html.txt")
    with open(fp, "w") as file:
        file.writelines(html_table)


def build_annual_table(df: pl.DataFrame) -> pl.DataFrame:
    return df.select(
        pl.col("Date"),
        pl.col("title").alias("Event"),
        # pl.col("price").alias("Price"),
        pl.col("genre").alias("Genre"),
        pl.col("suburb").alias("Suburb"),
        pl.col("state").alias("State"),
        pl.col("venue").alias("Venue"),
        pl.col("url").alias("Link"),
    )


@timer
@logger(filepath=save_path("gigs/data", "app.log"))
def build_tables():
    logging.warning(f"Running {os.path.basename(__file__)}")

    today, end_month, end_year = create_date_filters()
    omit_files = ("mtix_cache.json", "mtix_price.json", "mtix_venues.json")
    df = combine_tables(json_list=create_file_list(omit_files))

    df = (
        df.pipe(apply_formats)
        .pipe(add_columns)
        .pipe(apply_filter, today, end_year)
        .pipe(apply_sort)
        .pipe(remove_duplicate_rows)
    )

    # Build HTML table (30 days) | Conversion from polars to pandas
    save_to_text(df, "event_date", today, end_month)

    # Build CSV table (365 days)
    annual_table = build_annual_table(df)
    annual_table.write_csv(file=save_path("gigs/data_files", "annual_gigs.csv"))


if __name__ == "__main__":
    build_tables()
