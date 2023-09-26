import logging
import os
import sys
import unicodedata
from datetime import datetime

import selectolax
from pydantic import BaseModel, field_validator
from selectolax.parser import HTMLParser

from gigs.utils import (export_json, get_request, headers, logger, save_path,
                        timer)


class Gig(BaseModel):
    event_date: str = "-"
    title: str = "-"
    price: float = 0.0
    genre: str = "-"
    venue: str = "-"
    suburb: str = "-"
    state: str = "-"
    url: str = "-"
    image: str = "-"
    source: str = "Moshtix"

    @field_validator("title", "url")
    def remove_accents(cls, v):
        return unicodedata.normalize("NFD", v).encode("ascii", "ignore").decode("utf-8")


def build_date() -> tuple[str, str, int]:
    """
    Builds and returns the current date as a tuple of datetime objects.

    Returns:
        tuple[datetime, ...]: A tuple containing the current date as datetime objects.

    Example:
        ```python
        date = build_date()
        print(date)  # Output: (datetime.datetime, ...)
        ```
    """
    dt = datetime.now()
    return dt.strftime("%d"), dt.strftime("%b"), dt.year


def build_url(date_object: tuple[str, str, int]) -> str:
    day, month, year = date_object
    return f"https://moshtix.com.au/v2/search?query=&StateId=0&TimePeriod=6&FromDate={day}+{month}+{year}&FromDateDisplay={day}+{month}+{year}&ToDate=&ToDateDisplay=&CategoryList=2%2C&v2=0&Page="  # noqa


def end_page(base_url: str, node: str) -> int | None:
    """
    Returns the last page number from the given base URL and node.

    The function constructs a URL by appending '1' to the base URL. It then makes a
    request to the URL using the 'get_request' function with the provided headers. If
    the response is None, it logs an error and returns None. Otherwise, it parses the
    response HTML using the 'HTMLParser' class and extracts the text from the specified
    node. The text is stripped and split by spaces, and the last element is converted
    to an integer. The last page number is incremented by 1 and returned.

    Args:
        base_url (str): The base URL.
        node (str): The CSS selector for the node containing the page number.

    Returns:
        int | None: The last page number incremented by 1, or None if there was an
        error.

    Example:
        ```python
        base_url = "https://example.com/page="
        node = ".page-number"

        last_page = end_page(base_url, node)
        print(last_page)  # Output: 10
        ```
    """
    url = f"{base_url}1"
    response = get_request(url, headers)
    if response is None:
        logging.error(f"Error fetching response for {url}.")
        return None
    try:
        tree = HTMLParser(response.text)
        text = tree.css_first(node).text().strip().split(" ")
        return int(text[-1]) + 1
    except Exception as exc:
        logging.error(f"Error fetching last page: {exc}")
        return None


def extract_data(base_url: str, end_page: int, node_event: str):
    result = []
    for page_num in range(1, end_page):
        url = f"{base_url}{page_num}"
        response = get_request(url, headers)
        if response is None:
            logging.error(f"Error fetching response for {url}.")
            continue
        try:
            tree = HTMLParser(response.text)
            result.extend(tree.css(node_event))
        except Exception as exc:
            logging.error(f"Unable to extract event from HTML: {exc} ({url})")
    return result


def get_date(event: selectolax.parser.Node) -> str:
    node = event.css_first("h2.main-artist-event-header").child
    if node is None:
        return "-"
    text = node.text().replace("|", "").strip()  # Sat 16 Mar 2024, 7.30pm
    dt = text.replace(",", "").split(" ")  # ['Sat', '16', 'Mar', '2024', '7.30pm']
    return f"{dt[1]} {dt[2]} {dt[3]}" if len(dt) == 5 else text


def get_title(event: selectolax.parser.Node) -> str:
    return event.css_first("h2.main-event-header > a > span").text().strip()


def get_venue(event: selectolax.parser.Node) -> str:
    raw_string = event.css_first("h2.main-artist-event-header > a > span").text()
    return raw_string.replace("  ", " ").upper()


def get_url(event) -> str:
    return event.css_first("h2.main-event-header > a").attributes["href"]


def get_image(event) -> str:
    image_url = event.css_first("div.searchresult_image > a > img").attrs["src"]
    return f"https:{image_url}" if "https" not in image_url else image_url


def get_event(event_data: list[selectolax.parser.Node]) -> list[dict]:
    result = []
    for event in event_data:
        try:
            gig = Gig(
                event_date=get_date(event),
                title=get_title(event),
                venue=get_venue(event),
                url=get_url(event),
                image=get_image(event),
            )
            result.append(gig.model_dump())
        except Exception as exc:
            logging.error(f"Error unpacking event data from node: {exc}")
    return result


@timer
@logger(filepath=save_path("data", "app.log"))
def moshtix():
    logging.warning(f"Running {os.path.basename(__file__)}")
    NODE_PAGE = "section.moduleseparator"
    NODE_EVENT = "div.searchresult.clearfix"

    base_url = build_url(date_object=build_date())
    last_page = end_page(base_url, NODE_PAGE)
    if last_page is None:
        sys.exit(1)

    cache_data = extract_data(base_url, last_page, NODE_EVENT)
    result = get_event(cache_data)
    logging.warning(f"Found {len(result)} events.")
    export_json(result, filepath=save_path("data", "mtix_cache.json"))


if __name__ == "__main__":
    moshtix()
