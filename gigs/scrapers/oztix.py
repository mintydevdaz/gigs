import logging
import os
import sys
import unicodedata

import httpx
from pydantic import field_validator
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

    @field_validator("title")
    def remove_accents(cls, text):
        return (
            unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("utf-8")
        )


def create_data_cache(response: httpx.Response, json_key: str) -> list[dict] | None:
    if "application/json" in response.headers.get("content-type", ""):
        return response.json().get(json_key)
    return None


def get_prices(data: list[dict], price_tag: str):
    result = []
    with httpx.Client(headers=headers) as client:
        for event in data:
            url = event["url"]
            try:
                response = client.get(url)
                tree = HTMLParser(response.text)
                price = extract_ticket_price(tree, price_tag)
                event["price"] = "price"
                result.append(event)
            except Exception as exc:
                logging.error(f"Unable to extract price at URL '{url}': {exc}.")
                result.append(event)
    return result


def extract_ticket_price(html: HTMLParser, tag: str) -> float:
    nodes = html.css(tag)
    prices = [
        float(
            node.css_first(tag)
            .text()
            .strip()
            .replace("$", "")
            .replace(",", "")
        )
        for node in nodes
    ]
    return float(min(prices)) if prices else 0.0


def get_data(event_data: list[dict]) -> list[dict]:
    result = []
    for data in event_data:
        try:
            gig = OztixGig(
                date=data["dateStart"],  # ISO8601
                title=data["eventName"],
                venue=data["venue"]["name"],
                suburb=data["venue"]["locality"],
                state=data["venue"]["state"],
                url=data["eventUrl"],
                image=data["eventImage1"],
            )
            result.append(gig.model_dump())
        except Exception as exc:
            logging.error(f"Unable to fetch data: {exc} ({data.get('EventUrl', '-')})")
    return result


@timer
@logger(filepath=save_path("data", "app.log"))
def oztix():
    logging.warning(f"Running {os.path.basename(__file__)}")

    # CSS Selector
    PRICE_TAG = "div.ticket-price.hide-mobile"

    response = get_post_response(
        url="https://personalisationapi.oztix.com.au/api/recommendations",
        payload=payload,
    )
    if response is None:
        sys.exit(1)

    cache = create_data_cache(response, json_key="catalog")
    if cache is None:
        logging.error("No JSON data found.")
        sys.exit(1)

    initial_data = get_data(cache)
    final_data = get_prices(initial_data, PRICE_TAG)
    logging.warning(f"Found {len(final_data)} events.")

    export_json(final_data, filepath=save_path("data", "oztix.json"))


if __name__ == "__main__":
    oztix()
