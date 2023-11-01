import logging
import os
import sys
import unicodedata
from datetime import datetime

import selectolax
from pydantic import BaseModel, field_validator
from selectolax.parser import HTMLParser

from gigs.utils import (export_json, Gig, get_post_response, get_request, headers,
                        logger, payload, save_path, timer)


class OztixGig(Gig):
    source: str = "Oztix"

    @field_validator("date")
    def convert_date(cls, v):
        dt, time = v.split("T")
        parse_dt = datetime.strptime(dt, "%Y-%m-%d")
        return parse_dt.strftime("%d %b %Y")

    @field_validator("title")
    def remove_accents(cls, text):
        return (
            unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("utf-8")
        )


def get_price(url: str) -> float:
    """
    Fetches the price from a given URL.

    The function sends an HTTP GET request to the specified `url` with the provided
    `headers`. If the response is None, an error message is logged and 0.0 is returned.
    Otherwise, the HTML response is parsed using the `HTMLParser` class, and the
    extracted ticket price is returned. If any exceptions occur during the process, an
    error message is logged and 0.0 is returned.

    Args:
        url (str): The URL to fetch the price from.

    Returns:
        float: The fetched price, or 0.0 if an error occurs.

    Raises:
        Exception: If any error occurs during the fetching process.
    """
    response = get_request(url, headers)
    if response is None:
        logging.error(f"Error fetching price for {url}.")
        return 0.0
    try:
        tree = HTMLParser(response.text)
        return extract_ticket_price(tree)
    except Exception as exc:
        logging.error(f"Error fetching price for {url}: {exc}.")
        return 0.0


def extract_ticket_price(tree: selectolax.parser.HTMLParser) -> float:
    """
    Extracts the ticket price from the given HTMLParser tree.

    The function searches for nodes with the CSS selector "div.ticket-price.hide-mobile"
    in the provided `tree`. It extracts the text from each node, removes the "$" and ","
    characters, and converts the resulting strings to floats. The function returns the
    minimum price among the extracted prices, or 0.0 if no prices are found.

    Args:
        tree (selectolax.parser.HTMLParser): The HTMLParser tree to extract the ticket
        price from.

    Returns:
        float: The extracted ticket price, or 0.0 if no prices are found.
    """
    nodes = tree.css("div.ticket-price.hide-mobile")
    prices = [
        float(
            node.css_first("div.ticket-price.hide-mobile")
            .text()
            .strip()
            .replace("$", "")
            .replace(",", "")
        )
        for node in nodes
    ]
    return float(min(prices)) if prices else 0.0


def fetch_data(event_data: list[dict]) -> list[dict]:
    """
    Fetches data from a list of event dictionaries and creates Gig instances.

    The function iterates over each dictionary in the `event_data` list and attempts to
    extract relevant data to create a Gig instance. The extracted data includes event
    date, title, price (obtained using the `get_price` function), venue, suburb, state,
    URL, and image. If any exceptions occur during the process, an error message is
    logged. The function returns a list of dictionaries representing the dumped models
    of the created Gig instances.

    Args:
        event_data (list[dict]): A list of dictionaries containing event data.

    Returns:
        list[dict]: A list of dictionaries representing the dumped models of the
        created Gig instances.

    Raises:
        Exception: If any error occurs during the data extraction process.
    """
    result = []
    for data in event_data:
        try:
            url = data["eventUrl"]
            gig = OztixGig(
                date=data["dateStart"],
                title=data["eventName"],
                price=get_price(url),
                venue=data["venue"]["name"],
                suburb=data["venue"]["locality"],
                state=data["venue"]["state"],
                url=url,
                image=data["eventImage1"],
            )
            result.append(gig.model_dump())
        except Exception as exc:
            logging.error(f"Unable to fetch data: {exc} ({data.get('EventUrl')})")
    return result


@timer
@logger(filepath=save_path("data", "app.log"))
def oztix():
    logging.warning(f"Running {os.path.basename(__file__)}")

    # Fetch data
    url = "https://personalisationapi.oztix.com.au/api/recommendations"
    response = get_post_response(url, payload)
    if response is None:
        sys.exit(1)

    cache_data = response.json()
    event_data = cache_data.get("catalog")

    if event_data is None:
        logging.error("No event data found! Possible error fetching JSON data.")
        sys.exit(1)

    result = fetch_data(event_data)
    logging.warning(f"Found {len(result)} events.")
    export_json(result, filepath=save_path("data", "oztix.json"))


if __name__ == "__main__":
    oztix()
