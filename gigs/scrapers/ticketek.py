import logging
import os
import unicodedata

import httpx
from dateutil import parser
from pydantic import field_validator
from selectolax.parser import HTMLParser, Node

from gigs.utils import Gig, export_json, logger, save_path, timer


class TicketekGig(Gig):
    source: str = "Ticketek"

    @field_validator("title")
    def remove_accents(cls, text):
        return (
            unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("utf-8")
        )


def get_events(base_url: str, event_tag: str, end_page: int) -> list[Node]:
    events = []
    with httpx.Client() as client:
        for page in range(1, end_page):
            url = f"{base_url}{page}"
            try:
                response = client.get(url, follow_redirects=True)
                tree = HTMLParser(response.text)
                events.extend(tree.css(event_tag))
            except Exception as exc:
                logging.error(f"Error fetching data from URL '{url}': {exc}.")
    return events


def get_title(event: Node) -> str:
    title = event.css_first("h6")
    return "-" if title is None else title.text().strip()


def date_to_iso8601(date_object: Node) -> str:
    date_str = date_object.text().strip()  # Sat 02 Nov 2024
    try:
        parsed_date = parser.parse(date_str[:15])
        return parsed_date.isoformat()
    except ValueError:
        return "2099-01-01T00:00:00"


def get_date(event: Node, tag: str) -> str:
    date_object = event.css_first(tag)
    if date_object is None:
        return "2099-01-01T00:00:00"
    return date_to_iso8601(date_object)


def get_url(event: Node) -> str:
    base_url = "https://premier.ticketek.com.au"
    try:
        href = event.css_first("a").attributes["href"]
        return f"{base_url}{href}"
    except Exception:
        return "-"


def get_image(event: Node) -> str:
    try:
        image = event.css_first("img").attributes["src"]
        return f"https:{image}"
    except Exception:
        return "-"


def extract_venue_suburb_and_state(loc: list[str]) -> tuple[str, str, str]:
    if len(loc) != 4:
        return (loc[0], "-", loc[-1])
    venue = f"{loc[0]}, {loc[1]}"
    return venue, loc[2], loc[3]


def get_location(event: Node, location_tag: str) -> tuple[str, ...]:
    try:
        text = event.css_first(location_tag).text().strip()
        address = [i.strip() for i in text.split(",")]
        if len(address) == 3:
            return tuple(address)
        return extract_venue_suburb_and_state(address)
    except Exception as exc:
        return ("-", "-", "-")


def build_gig(
    event: Node,
    title: str,
    url: str,
    image: str,
    loc_tag: str,
    date_tag: str,
):
    venue, suburb, state = get_location(event, loc_tag)
    gig = TicketekGig(
        date=get_date(event, date_tag),
        title=title,
        venue=venue,
        suburb=suburb,
        state=state,
        url=url,
        image=image,
    )
    return gig.model_dump()


def get_data(
    events: list[Node],
    venue_tag: str,
    loc_tag: str,
    date_tag: str,
) -> list[dict]:
    result = []
    for event in events:
        title = get_title(event)
        url = get_url(event)
        image = get_image(event)

        gigs = [
            build_gig(show, title, url, image, loc_tag, date_tag)
            for show in event.css(venue_tag)
        ]
        result.extend(gigs)

    return result


@timer
@logger(filepath=save_path("data", "app.log"))
def ticketek():
    logging.warning(f"Running {os.path.basename(__file__)}")

    BASE_URL = "https://premier.ticketek.com.au/shows/genre.aspx?c=2048&page="
    END_PAGE = 24
    EVENT_TAG = "div.resultModule"
    DATE_TAG = "div.contentDate"
    VENUE_TAG = "div.contentEventAndDate.clearfix"
    LOC_TAG = "div.contentLocation"

    events = get_events(BASE_URL, EVENT_TAG, END_PAGE)
    data = get_data(events, VENUE_TAG, LOC_TAG, DATE_TAG)
    logging.warning(f"Found {len(data)} events.")
    export_json(data, filepath=save_path("data", "ticketek.json"))


if __name__ == "__main__":
    ticketek()
