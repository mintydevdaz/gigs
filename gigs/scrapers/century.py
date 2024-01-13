import logging
import os
import re
import sys
import unicodedata
from datetime import datetime
from typing import Any

import httpx
from pydantic import field_validator
from selectolax.parser import HTMLParser

from gigs.CONSTANTS import CENTURY_VENUES
from gigs.utils import (
    Gig,
    WebScraper,
    custom_headers,
    export_json,
    logger,
    save_path,
    timer,
)


class CenturyGig(Gig):
    source: str = "Century"

    @field_validator("date")
    def clean_date(cls, date_str):
        fmt = "%A, %d %B %Y %I:%M %p"  # Tuesday, 09 January 2024 07:00 PM
        return datetime.strptime(date_str, fmt).isoformat()

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


class CenturyScraper(WebScraper):
    def __init__(self) -> None:
        super().__init__()
        self.venues = CENTURY_VENUES
        self.headers = custom_headers
        self.event_card_tag = "div#row-inner-search > a"
        self._event_cards = self._get_event_cards()
        self.data = self._get_data()

    def _get_event_cards(self) -> list[dict[str, str]] | None:
        total_events = []
        with httpx.Client(headers=self.headers) as client:
            for venue in self.venues:
                url = venue["url"]

                # fetch events from each venue's webpage
                try:
                    r = client.get(url)
                    html = HTMLParser(r.text)
                    cards = html.css(self.event_card_tag)
                    total_events.extend(
                        {
                            "url": card.css_first("a").attributes["href"],
                            "name": venue["name"],
                            "suburb": venue["suburb"],
                            "state": venue["state"],
                        }
                        for card in cards
                    )
                except Exception as exc:
                    logging.error(f"Error scraping '{url}': {exc}.")

        if total_events:
            logging.warning(f"Found {len(total_events)} events.")
            return total_events
        else:
            return None

    def _get_data(self) -> list[dict[str, Any]] | None:
        if self._event_cards is None:
            return None

        result = []
        with httpx.Client(headers=self.headers) as client:
            for card in self._event_cards:
                url = card["url"]
                try:
                    r = client.get(url)
                    html = HTMLParser(r.text)
                    gig = self._build_event_object(card, html)
                    result.append(gig)
                except Exception as exc:
                    logging.error(f"Unable to get data from url '{url}': {exc}.")
        if result:
            logging.warning(f"Successfully parsed {len(result)} events.")
            return result
        else:
            return None

    def _build_event_object(self, card: dict[str, str], html: HTMLParser) -> dict:
        obj = CenturyGig(
            date=html.css_first("li.session-date").text(),
            title=html.css_first("h1.title").text(),
            price=self._get_price(text=self._extract_ticket_prices(html)),
            genre=self._get_genre(html),
            venue=card["name"],
            suburb=card["suburb"],
            state=card["state"],
            url=card["url"],
            image=self._get_image(html),
        )
        return obj.model_dump()

    def _get_price(self, text: str) -> float:
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

    def _extract_ticket_prices(self, html: HTMLParser) -> str:
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
        for text in html.css("ul.sessions"):
            try:
                item = text.css_first("li").text()
                result += item
            except AttributeError:
                continue
        return result

    def _get_genre(self, html: HTMLParser) -> str:
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

    def _get_image(self, html: HTMLParser) -> str:
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
            image_urls = img.css_first("style").text(strip=True).split(" ")
        return next(url for url in image_urls if "http" in url)  # type: ignore


@timer
@logger(filepath=save_path("data", "app.log"))
def century():
    logging.warning(f"Running {os.path.basename(__file__)}")
    data = CenturyScraper().data
    if data is None:
        sys.exit(1)
    export_json(data, filepath=save_path("data", "century.json"))


if __name__ == "__main__":
    century()
