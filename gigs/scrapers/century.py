import logging
import os
import re
import unicodedata
from datetime import datetime

import httpx
from pydantic import BaseModel, field_validator
from selectolax.parser import HTMLParser

from gigs.CONSTANTS import CENTURY_VENUES
from gigs.utils import export_json, get_request, headers, logger, save_path, timer


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
    source: str = "Century"

    @field_validator("event_date")
    def clean_date(cls, v):
        dt = v.split(" ")
        if len(dt) <= 4:
            return f"{dt[1]} {dt[2][:3]} {dt[3]}"
        parse_dt = datetime.strptime(f"{dt[1]} {dt[2]} {dt[3]}", "%d %B %Y")
        # return parse_dt.strftime("%d %b %Y")
        return parse_dt.isoformat()

    @field_validator("title")
    def remove_accents(cls, text):
        return (
            unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("utf-8")
        )

    @field_validator("genre")
    def clean_genre(cls, text):
        if "Music - " in text:
            return text.replace("Music - ", "").strip()
        elif "Comedy" in text:
            return "Comedy"
        elif "Arts" in text:
            return "Arts"
        elif "Other" in text:
            return text.replace("Other - ", "").strip()
        else:
            return "-"


def fetch_event_urls(venues: list[dict], tags: str) -> list[dict]:
    """
    Fetches event URLs from a list of venues based on specified tags.

    Args:
        venues (list[dict]): A list of dictionaries representing venues.
        tags (str): CSS selector tags used to filter event URLs.

    Returns:
        list[dict]: A list of dictionaries containing the fetched event URLs, along with venue information.

    Raises:
        Exception: If there is an error while fetching or scraping the event URLs.

    Examples:
        >>> venues = [
        ...     {
        ...         "url": "https://example.com/venue1",
        ...         "name": "Venue 1",
        ...         "suburb": "City 1",
        ...         "state": "State 1"
        ...     },
        ...     {
        ...         "url": "https://example.com/venue2",
        ...         "name": "Venue 2",
        ...         "suburb": "City 2",
        ...         "state": "State 2"
        ...     }
        ... ]
        >>> tags = ".event-card"
        >>> fetch_event_urls(venues, tags)
        [{'url': 'https://example.com/event1', 'name': 'Venue 1', 'suburb': 'City 1', 'state': 'State 1'},
        {'url': 'https://example.com/event2', 'name': 'Venue 2', 'suburb': 'City 2', 'state': 'State 2'}]
    """
    result = []
    for venue in venues:
        venue_url = venue["url"]
        response = get_request(venue_url, headers)
        if response is None:
            logging.error(f"Error fetching response for {venue_url}.")
            continue

        try:
            tree = HTMLParser(response.text)
            cards = tree.css(tags)
            result.extend(
                {
                    "url": card.css_first("a").attributes["href"],
                    "name": venue["name"],
                    "suburb": venue["suburb"],
                    "state": venue["state"],
                }
                for card in cards
            )
        except Exception as exc:
            logging.error(f"Error scraping {venue_url}: {exc}.")

    return result


def extract_ticket_prices(tree: HTMLParser) -> str:
    """
    Extracts ticket prices from an HTMLParser tree.

    Args:
        tree (HTMLParser): The HTMLParser tree representing the parsed HTML.

    Returns:
        str: The extracted ticket prices as a string.

    Examples:
        >>> html_tree = HTMLParser(html_content)
        >>> extract_ticket_prices(html_tree)
        'Ticket prices: $10 - $20'
    """
    result = ""
    for text in tree.css("ul.sessions"):
        try:
            item = text.css_first("li").text()
            result += item
        except AttributeError:
            continue
    return result


def fetch_price(text: str) -> float:
    """
    Fetches the minimum price from a string of text containing prices.

    Args:
        text (str): The text containing prices.

    Returns:
        float: The minimum price extracted from the text. Returns 0.0 if no prices are found.

    Examples:
        >>> text = "Ticket prices: $10, $15, $20"
        >>> fetch_price(text)
        10.0
    """
    result = re.findall(pattern=r"\d+\.\d+", string=text)
    if len(result) == 0:
        return 0.0
    prices = list(map(lambda i: float(i), result))
    return min(prices)


def fetch_genre(html: HTMLParser) -> str:
    """
    Fetches the genre from an HTMLParser object.

    Args:
        html (HTMLParser): The HTMLParser object representing the parsed HTML.

    Returns:
        str: The fetched genre. Returns "-" if the genre is not found.

    Examples:
        >>> html_tree = HTMLParser(html_content)
        >>> fetch_genre(html_tree)
        'Rock'
    """
    node = html.css_first("ul.category.inline-list").last_child
    return "-" if node is None else node.text().strip()


def fetch_image(html: HTMLParser) -> str:
    """
    Fetches the image URL from an HTMLParser object.

    Args:
        html (HTMLParser): The HTMLParser object representing the parsed HTML.

    Returns:
        str: The fetched image URL.

    Raises:
        StopIteration: If no image URL is found.

    Examples:
        >>> html_tree = HTMLParser(html_content)
        >>> fetch_image(html_tree)
        'https://example.com/image.jpg'
    """
    card = html.css("div#row-inner-event-hero > div.cell.small-24")
    for img in card:
        image_urls = img.css_first("style").text().strip().split(" ")
    return next(url for url in image_urls if "http" in url)  # type: ignore


def fetch_event_data(urls: list[dict]) -> list[dict]:
    result = []
    with httpx.Client(headers=headers) as client:
        for url in urls:
            try:
                response = client.get(url["url"])
                tree = HTMLParser(response.text)
                gig = Gig(
                    event_date=tree.css_first("li.session-date").text(),
                    title=tree.css_first("h1.title").text(),
                    price=fetch_price(text=extract_ticket_prices(tree)),
                    genre=fetch_genre(tree),
                    venue=url["name"],
                    suburb=url["suburb"],
                    state=url["state"],
                    url=url["url"],
                    image=fetch_image(tree),
                )
                result.append(gig.model_dump())
            except Exception as exc:
                logging.error(f"Unable to extract data from URL '{url['url']}': {exc}.")
    return result


@timer
@logger(filepath=save_path("data", "app.log"))
def century():
    logging.warning(f"Running {os.path.basename(__file__)}")
    CARD_TAG = "div#row-inner-search > a"
    urls = fetch_event_urls(venues=CENTURY_VENUES, tags=CARD_TAG)
    data = fetch_event_data(urls)
    logging.warning(f"Found {len(data)} events.")
    export_json(data, filepath=save_path("data", "century.json"))


if __name__ == "__main__":
    century()
