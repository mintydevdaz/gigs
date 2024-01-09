import logging
import os
import sys
import unicodedata

import httpx
from pydantic import field_validator
from selectolax.parser import HTMLParser

from gigs.utils import Gig, WebScraper, custom_headers, export_json, logger, save_path, timer


class OztixScraper(WebScraper):
    def __init__(self) -> None:
        super().__init__()
        self._url = "https://personalisationapi.oztix.com.au/api/recommendations"
        self._payload = {"options": {"use": 0, "geo": None, "postcode": None}}
        self._json_key = "catalog"
        self.raw_data = self._build_data_from_cache()

    def _create_data_cache(
        self, response: httpx.Response, json_key: str
    ) -> list[dict] | None:
        if "application/json" in response.headers.get("content-type", ""):
            return response.json().get(self._json_key)
        logging.error("No JSON data found.")
        return None

    def _get_json_data(self) -> list[dict] | None:
        r = self._get_post_response(self._url, self._payload)
        return None if r is None else self._create_data_cache(r, self._json_key)

    def _build_initial_dataset(self, event_data: list[dict]):
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
                logging.error(
                    f"Unable to fetch data: {exc} ({data.get('EventUrl', '-')})"
                )
        return result

    def _build_data_from_cache(self) -> list[dict] | None:
        event_data = self._get_json_data()
        return None if event_data is None else self._build_initial_dataset(event_data)


class OztixGig(Gig):
    source: str = "Oztix"

    @field_validator("title")
    def remove_accents(cls, text):
        return (
            unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("utf-8")
        )


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
    logging.warning(f"Found {len(result)} Oztix events.")
    return result


@timer
@logger(filepath=save_path("data", "app.log"))
def oztix():
    logging.warning(f"Running {os.path.basename(__file__)}")

    raw_data = OztixScraper().raw_data
    if raw_data is None:
        sys.exit(1)

    price_tag = "div.ticket-price.hide-mobile"
    final_data_with_prices = get_prices(raw_data, price_tag, custom_headers)

    destination_file = "oztix.json"
    export_json(final_data_with_prices, filepath=save_path("data", destination_file))


if __name__ == "__main__":
    oztix()
