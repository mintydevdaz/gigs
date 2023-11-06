import logging
import os
import re
import sys
import unicodedata
from datetime import datetime

import chompjs
import httpx
from pydantic import field_validator
from selectolax.parser import HTMLParser

from gigs.utils import Gig, export_json, get_request, custom_headers, logger, save_path, timer


class EventbriteGig(Gig):
    source: str = "Eventbrite"

    @field_validator("title")
    def remove_accents(cls, text):
        text = (
            unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("utf-8")
        )
        return text.strip()


def get_response_and_parse_html(url: str, headers: dict[str, str]) -> HTMLParser | None:
    response = get_request(url, headers)
    return None if response is None else HTMLParser(response.text)


def parse_javascript_text(html: HTMLParser, tag: str):
    script_tags = html.css(tag)
    text = "".join(script.text().strip() for script in script_tags).replace(" ", "")
    if match := re.search(pattern=r'"page_count":(\d{1,3})', string=text):
        return int(match[1]) + 1
    else:
        return None


def end_page(base_url: str, headers: dict[str, str], tag: str, page: int = 1) -> int | None:
    url = f"{base_url}{page}"
    html = get_response_and_parse_html(url, headers)
    if html is None:
        return None
    page_num = parse_javascript_text(html, tag)
    logging.warning(f"Last page number is {page_num}.")
    return None if page_num is None else page_num


def get_events(base_url: str, headers: dict[str, str], start_page: int, end_page: int, tag: str):
    events = []
    with httpx.Client(headers=headers) as client:
        for page in range(start_page, end_page):
            url = f"{base_url}{page}"
            try:
                response = client.get(url)
                tree = HTMLParser(response.text)
                if json_tags := tree.css(tag):
                    for json in json_tags:
                        data = chompjs.parse_js_object(json.text())
                        events.append(data)
            except Exception as exc:
                logging.error(f"Unable to parse JSON tag at URL '{url}': {exc}.")
    return events


def get_date(event: dict) -> str:
    try:
        date_str = event["startDate"]
        return datetime.strptime(date_str, "%Y-%m-%d").isoformat()
    except Exception:
        return "2099-01-01T00:00:00"


def get_location_info(event: dict) -> tuple[str, ...]:
    try:
        venue = event["location"]["name"]
        suburb = event["location"]["address"]["addressLocality"]
        state = event["location"]["address"]["addressRegion"]
        return venue, suburb, state
    except Exception:
        return "-", "-", "-"


def get_data(events: list[dict]) -> list[dict]:
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

    JS_TAG = 'script[type="text/javascript"]'
    JSON_TAG = "script[type='application/ld+json']"
    headers = custom_headers
    destination_cache_file = "eventbrite_cache.json"
    destination_data_file = "eventbrite.json"

    base_url = "https://www.eventbrite.com.au/d/australia/music--performances/?page="
    last_page = end_page(base_url, headers, JS_TAG)
    if last_page is None:
        logging.error("Unable to get last Eventbrite page.")
        sys.exit(1)

    cache_events = get_events(base_url, headers, 1, last_page, JSON_TAG)
    export_json(cache_events, filepath=save_path("cache", destination_cache_file))

    data = get_data(cache_events)
    logging.warning(f"Found {len(data)} events.")
    export_json(data, filepath=save_path("data", destination_data_file))


if __name__ == "__main__":
    eventbrite()
