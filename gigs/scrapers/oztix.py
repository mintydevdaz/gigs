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
    custom_headers,
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


def get_html(client: httpx.Client, url: str) -> HTMLParser | None:
    try:
        response = client.get(url)
        return HTMLParser(response.text)
    except httpx.HTTPError as exc:
        logging.error(f"Unable to get HTML at URL '{url}': {exc}.")
        return None


def extract_ticket_price(html: HTMLParser, tag: str) -> float:
    nodes = html.css(tag)
    prices = [
        float(node.css_first(tag).text().strip().replace("$", "").replace(",", ""))
        for node in nodes
    ]
    return float(min(prices)) if prices else 0.0


def extract_price_from_event(client: httpx.Client, event: dict, price_tag: str):
    tree = get_html(client, event["url"])
    if tree is not None:
        price = extract_ticket_price(tree, price_tag)
        event["price"] = price
    return event


def get_prices(data: list[dict], price_tag: str, headers: dict[str, str]) -> list[dict]:
    result = []
    with httpx.Client(headers=headers) as client:
        result.extend(
            extract_price_from_event(client, event, price_tag) for event in data
        )
    return result


@timer
@logger(filepath=save_path("data", "app.log"))
def oztix():
    logging.warning(f"Running {os.path.basename(__file__)}")

    PRICE_TAG = "div.ticket-price.hide-mobile"
    url = "https://personalisationapi.oztix.com.au/api/recommendations"
    json_key = "catalog"
    headers = custom_headers

    response = get_post_response(url, payload)
    if response is None:
        sys.exit(1)

    cache = create_data_cache(response, json_key)
    if cache is None:
        logging.error("No JSON data found.")
        sys.exit(1)

    initial_data = get_data(cache)
    final_data = get_prices(initial_data, PRICE_TAG, headers)
    logging.warning(f"Found {len(final_data)} events.")

    export_json(final_data, filepath=save_path("data", "oztix.json"))


if __name__ == "__main__":
    oztix()
