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
    WebScraper,
    custom_headers,
    export_json,
    logger,
    save_path,
    timer,
)


class SOHScraper(WebScraper):
    def __init__(self) -> None:
        super().__init__()
        self.home_url = "https://www.sydneyoperahouse.com"
        self.base_url = f"{self.home_url}/whats-on?page="
        self._headers = custom_headers
        self._card_tag = "div.soh-card.soh-card--whats-on.soh--card"
        self._date_tag = "time"
        self._title_tag = "span.soh-card__title-text"
        self._genre_tag = "p.soh-card__category"
        self._end_page = self._get_end_page()
        self._event_cards = self._get_event_cards()
        self.event_data = self._extract_event_data()

    def _extract_page_num(self, response: httpx.Response) -> int | None:
        tag = "li.pager__item.pager__item--last > a"
        html = HTMLParser(response.text)
        end_page = html.css_first(tag).attributes.get("href")
        if end_page is None:
            return None
        try:
            n = end_page.split("=")[-1]
            return int(n) + 1
        except ValueError as err:
            logging.error(f"Error extracting end page number: {err}.")
            return None

    def _get_end_page(self) -> int | None:
        url = f"{self.base_url}{0}"
        r = self._get_request(url, self._headers)
        return None if r is None else self._extract_page_num(r)

    def _get_event_cards(self) -> list[Node] | None:
        end_page = self._end_page
        if end_page is None:
            return None

        # Extract event cards
        result = []
        with httpx.Client(headers=self._headers) as client:
            for page in range(end_page):
                url = f"{self.base_url}{page}"
                try:
                    r = client.get(url)
                    html = HTMLParser(r.text)
                    result.extend(html.css(self._card_tag))
                except Exception as exc:
                    logging.error(f"Error fetching cards at URL '{url}': {exc}.")
        return result

    def _get_date(self, card: Node, date_tag: str) -> str:
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

    def _get_title(self, card: Node, title_tag: str) -> str:
        return card.css_first(title_tag).text().strip()

    def _get_genre(self, card: Node, genre_tag: str) -> str:
        return card.css_first(genre_tag).text()

    def _create_url(self, card: Node) -> str:
        href = card.css_first("a").attributes["href"]
        return f"{self.home_url}{href}"

    def _get_image(self, card: Node) -> str:
        src_link = card.css_first("img").attributes["src"]
        return f"{self.home_url}{src_link}"

    def _extract_event_data(self) -> list[dict] | None:
        cards = self._event_cards
        if cards is None:
            return None

        # Extract data from event cards
        result = []
        for card in cards:
            try:
                gig = SydneyOperaHouseGig(
                    date=self._get_date(card, self._date_tag),
                    title=self._get_title(card, self._title_tag),
                    genre=self._get_genre(card, self._genre_tag),
                    url=self._create_url(card),
                    image=self._get_image(card),
                )
                result.append(gig.model_dump())
            except Exception as exc:
                logging.error(f"Unable to retrieve card information: {exc}.")
        logging.warning(f"Found {result.__len__()} Sydney Opera House events.")
        return result


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


def format_date(date_str: str, format_str: str) -> str:
    return datetime.strptime(date_str, format_str).isoformat()


@timer
@logger(filepath=save_path("data", "app.log"))
def sydney_opera_house():
    logging.warning(f"Running {os.path.basename(__file__)}")

    data = SOHScraper().event_data
    if data is None:
        sys.exit(1)
    destination_file = "sydney_opera_house.json"
    export_json(data, filepath=save_path("data", destination_file))


if __name__ == "__main__":
    sydney_opera_house()
