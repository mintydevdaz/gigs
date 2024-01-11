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


class TicketekScraper:
    def __init__(self) -> None:
        self._last_page = 24
        self._event_tag = "div.resultModule"

    def get_events(self, base_url: str) -> list[Node]:
        total_events = []
        with httpx.Client() as client:
            for page in range(1, self._last_page):
                url = f"{base_url}{page}"
                try:
                    r = client.get(url, follow_redirects=True)
                    html = HTMLParser(r.text)
                    total_events.extend(html.css(self._event_tag))
                except Exception as exc:
                    logging.error(f"Error fetching data from url '{url}': {exc}.")
        logging.warning(f"Found {len(total_events)} event nodes.")
        return total_events


class TicketekEventData:
    def __init__(self) -> None:
        self._tag = {
            "date": "div.contentDate",
            "venue": "div.contentEventAndDate.clearfix",
            "location": "div.contentLocation",
        }

    def get_data(self, events: list[Node]):
        result = []
        for event in events:
            title = self._get_title(event)
            url = self._get_url(event)
            image = self._get_image(event)

            gigs = [
                self._build_individual_event(show, title, url, image)
                for show in event.css(self._tag["venue"])
            ]
            result.extend(gigs)
        logging.warning(f"Successfully parsed {len(result)} events.")
        return result

    def _get_title(self, event: Node) -> str:
        try:
            title = event.css_first("h6")
            return "-" if title is None else title.text(strip=True)
        except AttributeError as err:
            logging.error(f"Unable to parse Title in event: {err}")
            return "-"

    def _get_url(self, event: Node) -> str:
        base_url = "https://premier.ticketek.com.au"
        try:
            href = event.css_first("a").attributes["href"]
            return f"{base_url}{href}"
        except Exception:
            return "-"

    def _get_image(self, event: Node) -> str:
        try:
            image = event.css_first("img").attributes["src"]
            return f"https:{image}"
        except Exception:
            return "-"

    def _build_individual_event(self, event: Node, title: str, url: str, image: str):
        venue, suburb, state = self._get_location(
            event, location_tag=self._tag["location"]
        )
        gig = TicketekGig(
            date=self._get_date(event, tag=self._tag["date"]),
            title=title,
            venue=venue,
            suburb=suburb,
            state=state,
            url=url,
            image=image,
        )
        return gig.model_dump()

    def _get_location(self, event: Node, location_tag: str) -> tuple[str, ...]:
        try:
            text = event.css_first(location_tag).text().strip()
            address = [i.strip() for i in text.split(",")]
            if len(address) == 3:
                return tuple(address)
            return self._extract_venue_suburb_and_state(address)
        except Exception as exc:
            return ("-", "-", "-")

    def _extract_venue_suburb_and_state(self, loc: list[str]) -> tuple[str, str, str]:
        if len(loc) != 4:
            return (loc[0], "-", loc[-1])
        venue = f"{loc[0]}, {loc[1]}"
        return venue, loc[2], loc[3]

    def _get_date(self, event: Node, tag: str) -> str:
        date_object = event.css_first(tag)
        if date_object is None:
            return "2099-01-01T00:00:00"
        return self._date_to_iso8601(date_object)

    def _date_to_iso8601(self, date_object: Node) -> str:
        date_str = date_object.text().strip()  # Sat 02 Nov 2024
        try:
            parsed_date = parser.parse(date_str[:15])
            return parsed_date.isoformat()
        except ValueError:
            return "2099-01-01T00:00:00"


@timer
@logger(filepath=save_path("data", "app.log"))
def ticketek():
    logging.warning(f"Running {os.path.basename(__file__)}")

    base_url_for_concerts = (
        "https://premier.ticketek.com.au/shows/genre.aspx?c=2048&page="
    )
    events = TicketekScraper().get_events(base_url_for_concerts)
    data = TicketekEventData().get_data(events)
    export_json(data, filepath=save_path("data", "ticketek.json"))


if __name__ == "__main__":
    ticketek()
