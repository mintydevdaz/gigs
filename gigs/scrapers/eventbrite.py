import logging
import os
import re
import sys
import unicodedata
from datetime import datetime
from typing import Any

import chompjs
import httpx
from pydantic import field_validator
from selectolax.parser import HTMLParser

from gigs.utils import (
    Gig,
    WebScraper,
    custom_headers,
    export_json,
    logger,
    save_path,
    timer,
)


class EventbriteScraper(WebScraper):
    def __init__(self) -> None:
        super().__init__()
        self.base_url = (
            "https://www.eventbrite.com.au/d/australia/music--performances/?page="
        )
        self.headers = custom_headers
        self.json_tag = "script[type='application/ld+json']"
        self.javascript_tag = "script[type='text/javascript']"
        self.dest_cache_file = "eventbrite_cache.json"
        self.last_page = self._get_last_page()
        self.cache_data = self._get_events()

    def _get_last_page(self) -> int | None:
        start_page = 1
        url = f"{self.base_url}{start_page}"
        response = self._get_request(url, self.headers)
        if response is not None:
            return self._parse_javascript_text(response)
        logging.error("Unable to find last Eventbrite page.")
        return None

    def _parse_javascript_text(self, response: httpx.Response) -> int | None:
        html = HTMLParser(response.text)
        script_tags = html.css(self.javascript_tag)
        text = "".join(script.text().strip() for script in script_tags).replace(" ", "")
        if match := re.search(pattern=r'"page_count":(\d{1,3})', string=text):
            return int(match[1]) + 1
        else:
            return None

    def _get_events(self) -> list[dict[str, Any]] | None:
        if self.last_page is None:
            return None

        # Extract events from each web page
        total_events = []
        with httpx.Client(headers=self.headers) as client:
            for page in range(1, self.last_page):
                url = f"{self.base_url}{page}"
                try:
                    r = client.get(url)
                    html = HTMLParser(r.text)
                    if json_tags := html.css(self.json_tag):
                        for json in json_tags:
                            data_obj = chompjs.parse_js_object(json.text())
                            total_events.append(data_obj)
                except Exception as exc:
                    logging.error(f"Unable to parse JSON tag at URL '{url}': {exc}.")
        logging.warning(f"Found {len(total_events)} events.")
        self.export_json(
            data=total_events, filepath=save_path("cache", self.dest_cache_file)
        )
        return total_events


class EventbriteGig(Gig):
    source: str = "Eventbrite"

    @field_validator("title")
    def remove_accents(cls, text):
        text = (
            unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("utf-8")
        )
        return text.strip()


def get_location_info(event: dict) -> tuple[str, ...]:
    try:
        venue = event["location"]["name"]
        suburb = event["location"]["address"]["addressLocality"]
        state = event["location"]["address"]["addressRegion"]
        return venue, suburb, state
    except Exception:
        return "-", "-", "-"

def get_date(event: dict) -> str:
    try:
        date_str = event["startDate"]
        return datetime.strptime(date_str, "%Y-%m-%d").isoformat()
    except Exception:
        return "2099-01-01T00:00:00"


def parse_cache_data(events: list[dict[str, Any]]):
    data = []
    for event in events:
        venue, suburb, state = get_location_info(event)
        gig = EventbriteGig(
            date=get_date(event),
            title=event.get("name", "-"),
            venue=venue,
            suburb=suburb,
            state=state,
            url=event.get("url", "-"),
            image=event.get("image", "-"),
        )
        data.append(gig.model_dump())
    return data


@timer
@logger(filepath=save_path("data", "app.log"))
def eventbrite():
    logging.warning(f"Running {os.path.basename(__file__)}")
    bot = EventbriteScraper()
    raw_data = bot.cache_data
    if raw_data is None:
        sys.exit(1)

    clean_data = parse_cache_data(raw_data)
    export_json(clean_data, filepath=save_path("data", "eventbrite.json"))


if __name__ == "__main__":
    eventbrite()
