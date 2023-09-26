import logging
import re
import unicodedata
from datetime import datetime
import os

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
        return parse_dt.strftime("%d %b %Y")

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


def fetch_urls(venues: list[dict], tags: str) -> list[dict]:
    """
    Fetches URLs from a list of venues based on specified tags.

    This function takes a list of venue dictionaries and a CSS selector as input. It
    fetches the URLs of the venues based on the specified tags and returns a list of
    dictionaries containing the fetched URLs, venue names, suburbs, and states.

    Args:
        venues (list[dict]): A list of dictionaries representing venues.
        tags (str): CSS selector for selecting specific elements in the HTML.

    Returns:
        list[dict]: A list of dictionaries containing the fetched URLs, venue names,
        suburbs, and states.

    Raises:
        Exception: If there is an error fetching the response or scraping the data.

    Example:
        ```python
        venues = [
            {
                "url": "https://example.com/venue1",
                "name": "Venue 1",
                "suburb": "Suburb 1",
                "state": "State 1"
            },
            {
                "url": "https://example.com/venue2",
                "name": "Venue 2",
                "suburb": "Suburb 2",
                "state": "State 2"
            }
        ]
        tags = ".card"

        result = fetch_urls(venues, tags)
        print(result)
        ```
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


def extract_ticket_prices(tree) -> str:
    """Extracts all the prices present on webpage."""
    result = ""
    for text in tree.css("ul.sessions"):
        try:
            item = text.css_first("li").text()
            result += item
        except AttributeError:
            continue
    return result


def fetch_price(text: str) -> float:
    """Identifies the lowest price within subset of text string of prices."""
    result = re.findall(pattern=r"\d+\.\d+", string=text)
    if len(result) == 0:
        return 0.0
    prices = list(map(lambda i: float(i), result))
    return min(prices)


def fetch_genre(tree: HTMLParser) -> str:
    node = tree.css_first("ul.category.inline-list").last_child
    return "-" if node is None else node.text().strip()


def fetch_image(tree) -> str:
    card = tree.css("div#row-inner-event-hero > div.cell.small-24")
    for img in card:
        image_urls = img.css_first("style").text().strip().split(" ")
    return next(url for url in image_urls if "http" in url)  # type: ignore


def fetch_data(urls: list[dict]) -> list[dict]:
    result = []
    for url in urls:
        response = get_request(url["url"], headers)
        if response is None:
            logging.error(f"Error fetching response for {url['url']}.")
            continue

        try:
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
            logging.error(f"Unable to extract data from url: {exc} ({url}).")
    return result


@timer
@logger(filepath=save_path("data", "app.log"))
def century():
    logging.warning(f"Running {os.path.basename(__file__)}")
    CARD_TAG = "div#row-inner-search > a"
    urls = fetch_urls(venues=CENTURY_VENUES, tags=CARD_TAG)
    data = fetch_data(urls)
    logging.warning(f"Found {len(data)} events.")
    export_json(data, filepath=save_path("data", "century.json"))


if __name__ == "__main__":
    century()