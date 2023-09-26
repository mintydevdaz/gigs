import logging
import os
import re
import sys
import unicodedata
from datetime import datetime

import chompjs
from pydantic import BaseModel, Field, field_validator
from selectolax.parser import HTMLParser

from gigs.utils import (export_json, get_request, headers, logger, save_path,
                        timer)


class Gig(BaseModel):
    event_date: str = Field(default="01 Jan 2099")
    title: str = "-"
    price: float = 0.0
    genre: str = "-"
    venue: str = "-"
    suburb: str = "-"
    state: str = "-"
    url: str = "-"
    image: str = Field(default="-")
    source: str = "Eventbrite"

    @field_validator("event_date")
    def parse_date(cls, v):
        dt_object = datetime.strptime(v, "%Y-%m-%d")
        return dt_object.strftime("%d %b %Y")

    @field_validator("price")
    def convert_price(cls, v):
        return float(v) if isinstance(v, str) else 0.0

    @field_validator("title", "venue")
    def remove_accents(cls, text):
        text = (
            unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("utf-8")
        )
        return text.strip()


def pagination(base_url: str, page_num: int, tag: str) -> int | None:
    """
    Fetches the pagination count for a given base URL, page number, and tag.

    Args:
        base_url (str): The base URL.
        page_num (int): The page number.
        tag (str): The CSS selector for the tag.

    Returns:
        int | None: The pagination count if found, None otherwise.
    """
    url = f"{base_url}{page_num}"
    response = get_request(url, headers)
    if response is None:
        logging.error(f"Error fetching response for {url}.")
        return None

    try:
        tree = HTMLParser(response.text)
        script_tags = tree.css(tag)
        text = "".join(script.text().strip() for script in script_tags).replace(" ", "")
        if match := re.search(pattern=r'"page_count":(\d{1,3})', string=text):
            return int(match[1]) + 1
    except Exception as exc:
        logging.error(f"Unable to find last Eventbrite page: {exc}")
        return None


def fetch_events(base_url: str, start_page: int, end_page: int, tag: str):
    """
    Fetches events from a given base URL within a specified range of pages, using a
    specified tag.

    The function sends HTTP GET requests to each page within the range of `start_page`
    and `end_page` (exclusive). It parses the HTML response using the `HTMLParser`
    class and extracts script tags that match the specified `tag`. Each script tag is
    then parsed using `chompjs.parse_js_object()` to obtain a JSON object, which is
    appended to the `result` list. If any exceptions occur during the process, an error
    message is logged. The function returns the `result` list.

    Args:
        base_url (str): The base URL to fetch events from.
        start_page (int): The starting page number (inclusive).
        end_page (int): The ending page number (exclusive).
        tag (str): The CSS selector tag to match script tags.

    Returns:
        list: A list of JSON objects representing the fetched events.

    Raises:
        Exception: If any error occurs during the fetching process.
    """
    result = []
    for page_num in range(start_page, end_page):
        url = f"{base_url}{page_num}"
        response = get_request(url, headers)
        if response is None:
            logging.error(f"Error fetching response for {url}.")
            continue

        try:
            tree = HTMLParser(response.text)
            if script_tags := tree.css(tag):
                for script_tag in script_tags:
                    json_object = chompjs.parse_js_object(script_tag.text())
                    result.append(json_object)
        except Exception as exc:
            logging.error(f"Unable to extract data from url: {exc} ({url}).")
    return result


def fetch_data(json_data: list[dict]) -> list[dict]:
    """
    Fetches data from a list of JSON objects and creates Gig instances.

    The function iterates over each JSON object in the `json_data` list and attempts to
    extract relevant data to create a Gig instance. The extracted data includes event
    date, title, price, venue, suburb, state, URL, and image. If any exceptions occur
    during the process, an error message is logged. The function returns a list of
    dictionaries representing the dumped models of the created Gig instances.

    Args:
        json_data (list[dict]): A list of JSON objects containing event data.

    Returns:
        list[dict]: A list of dictionaries representing the dumped models of the
        created Gig instances.

    Raises:
        Exception: If any error occurs during the data extraction process.
    """
    result = []
    for data in json_data:
        try:
            gig = Gig(
                event_date=data["startDate"],
                title=data["name"],
                price=data["offers"].get("lowPrice"),
                venue=data["location"].get("name"),
                suburb=data["location"]["address"].get("addressLocality"),
                state=data["location"]["address"].get("addressRegion"),
                url=data["url"],
                image=data.get("image", "-"),
            )
            result.append(gig.model_dump())
        except Exception as exc:
            logging.error(f"Unable to extract data: {exc}")
    return result


@timer
@logger(filepath=save_path("data", "app.log"))
def eventbrite():
    logging.warning(f"Running {os.path.basename(__file__)}")

    JS_TAG = 'script[type="text/javascript"]'
    JSON_TAG = "script[type='application/ld+json']"

    base_url = "https://www.eventbrite.com.au/d/australia/music--events/%23music/?page="
    end_page = pagination(base_url, page_num=1, tag=JS_TAG)
    if end_page is None:
        sys.exit()

    cached_data = fetch_events(base_url, start_page=1, end_page=end_page, tag=JSON_TAG)
    result = fetch_data(cached_data)
    logging.warning(f"Found {len(result)} events.")
    export_json(result, filepath=save_path("data", "eventbrite.json"))


if __name__ == "__main__":
    eventbrite()
