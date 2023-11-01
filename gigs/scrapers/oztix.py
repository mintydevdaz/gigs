import logging
import os
import sys
import unicodedata
from datetime import datetime

from pydantic import BaseModel, field_validator
from selectolax.parser import HTMLParser

from gigs.utils import (
    Gig,
    export_json,
    get_post_response,
    get_request,
    headers,
    logger,
    payload,
    save_path,
    timer,
)


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


def extract_ticket_price(tree: HTMLParser) -> float:
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
