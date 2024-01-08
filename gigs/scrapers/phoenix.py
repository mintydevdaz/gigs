import logging
import os
import sys
import unicodedata
from datetime import datetime

import httpx
from pydantic import field_validator
from selectolax.parser import HTMLParser

from gigs.utils import Gig, WebScraper, custom_headers, logger, save_path


class PhoenixGig(Gig):
    genre: str = "Contemporary"
    venue: str = "Phoenix Central Park"
    suburb: str = "Chippendale"
    state: str = "NSW"
    source: str = "Phoenix Central Park"

    @field_validator("date")
    def clean_date(cls, date_str):
        fmt = "%d %b %Y"
        return format_date(date_str, fmt)

    @field_validator("title")
    def remove_accents(cls, text):
        return (
            unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("utf-8")
        )


def format_date(date_str: str, fmt: str) -> str:
    if "—" not in date_str:
        return datetime.strptime(date_str, fmt).isoformat()
    split = date_str.split("—")  # an 'em dash', not a hyphen | 1—4 Nov 2023
    new_date = f"{split[0]}{split[1][1:]}"
    return datetime.strptime(new_date, fmt).isoformat()


def get_image(html: HTMLParser, tag: str) -> str:
    meta_tag = html.css_first(tag)
    return meta_tag.attrs.get("content", "-")


class PhoenixScraper(WebScraper):
    def __init__(self) -> None:
        super().__init__()
        self.base_url = "https://phoenixcentralpark.com.au"
        self.headers = custom_headers
        self.current_season_url = self._get_season_url(self.base_url, self.headers)

    def _get_season_url(self, base_url: str, headers: dict[str, str]) -> str | None:
        r = self._get_request(base_url, headers)
        if r is None:
            return None
        try:
            html = HTMLParser(r.text)
            href = next(
                (
                    link.attributes["href"]
                    for link in html.css("div.header-nav-folder-item > a")
                    if "season" in link.text().lower()
                ),
                "",
            )
            return f"{base_url}{href}"
        except Exception as exc:
            logging.error(f"Unable to fetch season url: {exc}.")
            return None

    def _build_event_links(self, html: HTMLParser, base_url: str) -> list[str] | None:
        if links := html.css("a.sqs-block-image-link"):
            hrefs = [
                link.css_first("a").attrs.get("href")
                for link in links
                if link.css_first("a").attrs.get("href") is not None
            ]
            return [f"{base_url}{href}" for href in hrefs if "https" not in href]
        else:
            logging.error("No links for individual events found.")
            return None

    def get_event_urls(self, season_url: str) -> list[str] | None:
        r = self._get_request(season_url, self.headers)
        if r is None:
            return None
        html = HTMLParser(r.text)
        return self._build_event_links(html, self.base_url)

    def get_event_data(
        self, event_urls: list[str], title_tag: str, date_tag: str, image_tag: str
    ) -> list[dict]:
        result = []
        with httpx.Client(headers=self.headers) as client:
            for url in event_urls:
                try:
                    r = client.get(url, headers=self.headers)
                    html = HTMLParser(r.text)
                    gig = PhoenixGig(
                        date=html.css_first(date_tag).text(),
                        title=html.css_first(title_tag).text(),
                        url=url,
                        image=get_image(html, image_tag),
                    )
                    result.append(gig.model_dump())
                except Exception as exc:
                    logging.error(f"Unable to extract data from URL '{url}': {exc}.")
        return result


@logger(filepath=save_path("data", "app.log"))
def phoenix():
    logging.warning(f"Running {os.path.basename(__file__)}")

    # Tag variables
    image_tag = "meta[property='og:image']"
    title_tag = "div.sqs-html-content > h3"
    date_tag = "div.sqs-html-content > h4"

    # The cool stuff happens here :)
    scraper = PhoenixScraper()
    season_url = scraper.current_season_url
    if season_url is None:
        sys.exit(1)

    event_urls = scraper.get_event_urls(season_url)
    if event_urls is None:
        sys.exit(1)

    data = scraper.get_event_data(event_urls, title_tag, date_tag, image_tag)
    scraper.export_json(data, filepath=save_path("data", "phoenix.json"))


if __name__ == "__main__":
    phoenix()
