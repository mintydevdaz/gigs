import logging
import os
import sys
import unicodedata

import selectolax
from pydantic import BaseModel, field_validator
from selectolax.parser import HTMLParser

from gigs.utils import export_json, get_request, headers, logger, save_path, timer


class Gig(BaseModel):
    event_date: str
    title: str = "-"
    price: float = 0.0
    genre: str = "-"
    venue: str = "Sydney Opera House"
    suburb: str = "Sydney"
    state: str = "NSW"
    url: str = "-"
    image: str = "-"
    source: str = "Sydney Opera House"

    @field_validator("event_date")
    def clean_date(cls, v):
        return f"0{v}" if v[1].isspace() else v

    @field_validator("title")
    def remove_accents(cls, text):
        return (
            unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("utf-8")
        )


def find_last_page(base_url: str) -> int | None:
    url = f"{base_url}{0}"
    response = get_request(url, headers)
    if response is None:
        logging.error(f"Error fetching response for {url}.")
        return None
    tree = HTMLParser(response.text)
    return get_page_num(tree)


def get_page_num(tree: HTMLParser) -> int | None:
    """
    Returns the page number extracted from the given HTMLParser tree.

    Args:
        tree (HTMLParser): The HTMLParser tree containing the page information.

    Returns:
        int | None: The extracted page number, incremented by 1. Returns None if the
        page number cannot be extracted.

    Raises:
        ValueError: Raised when the extracted page number cannot be converted to an
        integer.

    Example:
        ```python
        tree = HTMLParser()
        page_num = get_page_num(tree)
        if page_num is not None:
            print(f"Page number: {page_num}")
        else:
            print("Failed to extract page number.")
        ```
    """
    node = "li.pager__item.pager__item--last > a"
    end_page = tree.css_first(node).attributes.get("href")
    if end_page is None:
        return None
    try:
        n = end_page.split("=")[-1]
        return int(n) + 1
    except ValueError as e:
        logging.error(f"Error extracing end page number: {e}")
        return None


def get_event_cards(base_url: str, end_page: int, node_card: str) -> list:
    """
    Retrieves event cards from the specified base URL and range of pages.

    Args:
        base_url (str): The base URL for the event cards.
        end_page (int): The end page number (exclusive) to retrieve event cards from.
        node_card (str): The CSS selector for the event card elements.

    Returns:
        list: A list of event cards retrieved from the specified pages.

    Example:
        ```python
        base_url = "https://www.example.com/events?page="
        end_page = 5
        node_card = ".event-card"
        event_cards = get_event_cards(base_url, end_page, node_card)
        for card in event_cards:
            print(card)
        ```
    """
    results = []
    for page_num in range(end_page):
        url = f"{base_url}{page_num}"
        response = get_request(url, headers)
        if response is not None:
            try:
                tree = HTMLParser(response.text)
                results.extend(tree.css(node_card))
            except Exception as exc:
                logging.error(f"Error fetching cards: {exc}")
    return results


def fetch_date(card: selectolax.parser.Node, node_date: str) -> str:
    """
    Fetches the date from a given card using the specified node_date.

    Args:
        card (selectolax.parser.Node): The card from which to fetch the date.
        node_date (str): The CSS selector for the date node.

    Returns:
        str: The fetched date, stripped of leading and trailing whitespace.
    """
    date = card.css(node_date)
    return date[-1].text().strip()


def fetch_title(card: selectolax.parser.Node, node_title: str) -> str:
    title = card.css_first(node_title)
    return title.text().strip()


def fetch_genre(card: selectolax.parser.Node, node_genre: str) -> str:
    genre = card.css_first(node_genre)
    return genre.text()


def fetch_url(card: selectolax.parser.Node, base_url: str) -> str:
    href = card.css_first("a").attributes["href"]
    return f"{base_url}{href}"


def fetch_image(card: selectolax.parser.Node, base_url: str) -> str:
    src_link = card.css_first("img").attributes["src"]
    return f"{base_url}{src_link}"


def fetch_card_data(
    cards: list, node_date: str, node_title: str, node_genre: str
) -> list[dict]:
    """
    Fetches card data from the specified list of cards.

    Args:
        cards (list): A list of cards to fetch data from.
        node_date (str): The CSS selector for the date element in each card.
        node_title (str): The CSS selector for the title element in each card.
        node_genre (str): The CSS selector for the genre element in each card.

    Returns:
        list[dict]: A list of dictionaries containing the fetched card data.

    Example:
        ```python
        cards = [
            {"date": "2022-01-01", "title": "Event 1", "genre": "Music"},
            {"date": "2022-01-02", "title": "Event 2", "genre": "Theater"},
        ]
        node_date = ".card-date"
        node_title = ".card-title"
        node_genre = ".card-genre"
        card_data = fetch_card_data(cards, node_date, node_title, node_genre)
        for card in card_data:
            print(card)
        ```
    """
    base_url = "https://www.sydneyoperahouse.com"
    result = []
    for card in cards:
        try:
            gig = Gig(
                event_date=fetch_date(card, node_date),
                title=fetch_title(card, node_title),
                genre=fetch_genre(card, node_genre),
                url=fetch_url(card, base_url),
                image=fetch_image(card, base_url),
            )
            result.append(gig.model_dump())
        except Exception as exc:
            logging.error(f"Unable to retrieve card info: {exc}")
    return result


@timer
@logger(filepath=save_path("data", "app.log"))
def sydney_opera_house():
    logging.warning(f"Running {os.path.basename(__file__)}")

    NODE_CARD = "div.soh-card.soh-card--whats-on.soh--card"
    NODE_DATE = "time"
    NODE_TITLE = "span.soh-card__title-text"
    NODE_GENRE = "p.soh-card__category"

    base_url = "https://www.sydneyoperahouse.com/whats-on?page="
    end_page = find_last_page(base_url)
    if end_page is None:
        sys.exit(1)

    cards = get_event_cards(base_url, end_page, NODE_CARD)
    if not len(cards):
        logging.error("No events found on page.")
        sys.exit(1)

    data = fetch_card_data(cards, NODE_DATE, NODE_TITLE, NODE_GENRE)
    logging.warning(f"Found {len(data)} events.")
    export_json(data, filepath=save_path("data", "sydney_opera_house.json"))


if __name__ == "__main__":
    sydney_opera_house()
