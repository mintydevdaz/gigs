import logging
import os
import sys
import unicodedata
from datetime import datetime

import httpx
from pydantic import field_validator
from selectolax.parser import HTMLParser, Node

from gigs.utils import (
    Gig,
    custom_headers,
    export_json,
    get_request,
    logger,
    save_path,
    timer,
)


class SydneyOperaHouseGig(Gig):
    venue: str = "Sydney Opera House"
    suburb: str = "Sydney"
    state: str = "NSW"
    source: str = "Sydney Opera House"

    @field_validator("date")
    def clean_date(cls, date_str):
        fmt = "%d %b %Y"
        return (
            format_date(f"0{date_str}", fmt)
            if date_str[1].isspace()
            else format_date(date_str, fmt)
        )

    @field_validator("title")
    def remove_accents(cls, text):
        return (
            unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("utf-8")
        )


def page_num(html: HTMLParser) -> int | None:
    tag = "li.pager__item.pager__item--last > a"
    end_page = html.css_first(tag).attributes.get("href")
    if end_page is None:
        return None
    try:
        n = end_page.split("=")[-1]
        return int(n) + 1
    except ValueError as e:
        logging.error(f"Error extracing end page number: {e}")
        return None


def find_last_page(base_url: str, headers: dict[str, str]) -> int | None:
    url = f"{base_url}{0}"
    response = get_request(url, headers)
    if response is None:
        logging.error(f"Error fetching response for {url}.")
        return None
    tree = HTMLParser(response.text)
    return page_num(tree)


def get_event_cards(base_url: str, headers: dict[str, str], end_page: int, tag: str) -> list[Node]:
    result = []
    with httpx.Client(headers=headers) as client:
        for page_num in range(end_page):
            url = f"{base_url}{page_num}"
            try:
                response = client.get(url)
                tree = HTMLParser(response.text)
                result.extend(tree.css(tag))
            except Exception as exc:
                logging.error(f"Error fetching cards at URL '{url}': {exc}.")
    return result


def format_date(date_str: str, format_str: str) -> str:
    return datetime.strptime(date_str, format_str).isoformat()


def get_date(card: Node, date_tag: str) -> str:
    """
    Fetches the date from a given card using the specified node_date.

    Args:
        card (selectolax.parser.Node): The card from which to fetch the date.
        node_date (str): The CSS selector for the date node.

    Returns:
        str: The fetched date, stripped of leading and trailing whitespace.
    """
    date = card.css(date_tag)
    return date[-1].text().strip()


def get_title(card: Node, title_tag: str) -> str:
    return card.css_first(title_tag).text().strip()


def get_genre(card: Node, genre_tag: str) -> str:
    return card.css_first(genre_tag).text()


def create_url(card: Node, base_url: str) -> str:
    href = card.css_first("a").attributes["href"]
    return f"{base_url}{href}"


def get_image(card: Node, base_url: str) -> str:
    src_link = card.css_first("img").attributes["src"]
    return f"{base_url}{src_link}"


def get_data(cards: list, date_tag: str, title_tag: str, genre_tag: str) -> list[dict]:
    base_url = "https://www.sydneyoperahouse.com"
    result = []
    for card in cards:
        try:
            gig = SydneyOperaHouseGig(
                date=get_date(card, date_tag),
                title=get_title(card, title_tag),
                genre=get_genre(card, genre_tag),
                url=create_url(card, base_url),
                image=get_image(card, base_url),
            )
            result.append(gig.model_dump())
        except Exception as exc:
            logging.error(f"Unable to retrieve card info: {exc}")
    return result


@timer
@logger(filepath=save_path("data", "app.log"))
def sydney_opera_house():
    logging.warning(f"Running {os.path.basename(__file__)}")

    CARD_TAG = "div.soh-card.soh-card--whats-on.soh--card"
    DATE_TAG = "time"
    TITLE_TAG = "span.soh-card__title-text"
    GENRE_TAG = "p.soh-card__category"
    headers = custom_headers
    base_url = "https://www.sydneyoperahouse.com/whats-on?page="

    end_page = find_last_page(base_url, headers)
    if end_page is None:
        sys.exit(1)

    cards = get_event_cards(base_url, headers, end_page, CARD_TAG)
    if not len(cards):
        logging.error("No events found on page.")
        sys.exit(1)

    data = get_data(cards, DATE_TAG, TITLE_TAG, GENRE_TAG)
    logging.warning(f"Found {len(data)} events.")

    export_json(data, filepath=save_path("data", "sydney_opera_house.json"))


if __name__ == "__main__":
    sydney_opera_house()
