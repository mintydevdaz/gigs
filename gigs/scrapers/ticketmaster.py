import logging
import os
import sys
import time
import unicodedata
from datetime import datetime

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, field_validator

from gigs.utils import export_json, logger, save_path, timer


class Gig(BaseModel):
    event_date: str = "-"
    title: str = "-"
    price: float = 0.0
    genre: str = "Music"
    venue: str = "-"
    suburb: str = "-"
    state: str = "-"
    url: str = "-"
    image: str = "-"
    source: str = "Ticketmaster"

    @field_validator("event_date")
    def convert_date(cls, v):
        dt = datetime.strptime(v, "%Y-%m-%d")
        return dt.isoformat()

    @field_validator("title")
    def remove_accents(cls, text):
        return (
            unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("utf-8")
        )


def total_pages(api_key: str) -> int | None:
    url = f"https://app.ticketmaster.com/discovery/v2/events.json?classificationName=music&countryCode=AU&page=0&apikey={api_key}"  # noqa
    try:
        response = httpx.get(url)
        data = response.json()
        return data.get("page").get("totalPages")
    except Exception as exc:
        logging.error(f"Error fetching API response: {exc}")
        return None


def extract_events(api_key: str, page_num: int) -> list:
    result = []
    for num in range(page_num + 1):
        try:
            url = f"https://app.ticketmaster.com/discovery/v2/events.json?classificationName=music&countryCode=AU&page={num}&apikey={api_key}"  # noqa
            time.sleep(1)
            response = httpx.get(url)
            data = response.json()["_embedded"]["events"]
            result.extend(data)
        except Exception as exc:
            logging.error(f"Unable to extract data from JSON: {exc}")
    return result


def get_min_price(data: dict) -> float:
    """
    Returns the minimum price from the given data.

    The function retrieves the "priceRanges" from the data dictionary. If the
    "priceRanges" is None, it returns 0.0. Otherwise, it finds the minimum value of
    "min" from the "priceRanges" where "min" is not equal to 0. The minimum price is
    then converted to a float if it is either a float or a string, otherwise it returns
    0.0.

    Args:
        data (dict): A dictionary containing the data.

    Returns:
        float: The minimum price.

    Example:
        ```python
        data = {
            "priceRanges": [
                {"min": 10.0},
                {"min": "15.0"},
                {"min": 20},
                {"min": 0},
            ]
        }

        min_price = get_min_price(data)
        print(min_price)  # Output: 10.0
        ```
    """
    prices = data.get("priceRanges")
    if prices is None:
        return 0.0
    price = min(num.get("min") for num in prices if num.get("min") != 0)
    return float(price) if isinstance(price, (float, str)) else 0.0


def fetch_data(cache_data: list[dict]) -> list[dict]:
    result = []
    for data in cache_data:
        url = data.get("url", "-")
        venue = data["_embedded"]["venues"][0]
        try:
            gig = Gig(
                event_date=data["dates"]["start"]["localDate"],
                title=data["name"],
                price=get_min_price(data),
                venue=venue["name"],
                suburb=venue["city"]["name"],
                state=venue["state"]["stateCode"],
                url=url,
                image=data["images"][0]["url"],
            )
            result.append(gig.model_dump())
        except Exception as exc:
            logging.error(f"Unable to fetch data from URL '{url}': {exc}.")
    return result


@timer
@logger(filepath=save_path("data", "app.log"))
def ticketmaster():
    logging.warning(f"Running {os.path.basename(__file__)}")
    load_dotenv()
    api_key = str(os.getenv("TM_KEY"))

    page_num = total_pages(api_key)  # type: ignore
    if page_num is None:
        sys.exit()

    cache_data = extract_events(api_key, page_num)
    result = fetch_data(cache_data)
    logging.warning(f"Found {len(result)} events.")
    export_json(result, filepath=save_path("data", "ticketmaster.json"))


if __name__ == "__main__":
    ticketmaster()
