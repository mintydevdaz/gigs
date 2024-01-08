import logging
import os
import sys

import httpx
from dotenv import load_dotenv
from gigs.utils import Gig, WebScraper, logger, save_path, timer


class TicketmasterScraper(WebScraper):
    def __init__(self) -> None:
        super().__init__()
        load_dotenv()
        self._api_key = str(os.getenv("TM_KEY"))
        self.end_page = self._get_end_page(self._api_key)

    def _get_end_page(self, api_key: str) -> int | None:
        url = f"https://app.ticketmaster.com/discovery/v2/events.json?classificationName=music&countryCode=AU&page=0&apikey={api_key}"  # noqa
        try:
            json = httpx.get(url).json()
            return json["page"]["totalPages"]
        except Exception as exc:
            logging.error(f"Error fetching end page from JSON: {exc}.")
            return None

    def get_events(self, end_page: int, cache_file: str) -> list[dict] | None:
        events = []
        with httpx.Client() as client:
            for page in range(end_page):
                url = f"https://app.ticketmaster.com/discovery/v2/events.json?classificationName=music&countryCode=AU&page={page}&apikey={self._api_key}"  # noqa
                try:
                    json = client.get(url).json()["_embedded"]["events"]
                    events.extend(json)
                except Exception as exc:
                    logging.error(f"Error fetching JSON '{url}': {exc}.")
        if not events:
            return None
        logging.warning(f"Found {events.__len__()} Ticketmaster events.")
        self.export_json(events, filepath=save_path("data", cache_file))
        return events

    def get_data(self, events: list[dict], data_file: str) -> None:
        result = []
        for event in events:
            url = event.get("url", "-")
            venue, suburb, state = get_location_info(event)
            try:
                gig = TicketmasterGig(
                    date=get_date(event),
                    title=event.get("name", "-"),
                    price=get_lowest_price(event),
                    venue=venue,
                    suburb=suburb,
                    state=state,
                    url=url,
                    image=get_image(event),
                )
                result.append(gig.model_dump())
            except Exception as exc:
                logging.error(f"Error parsing data for '{url}': {exc}.")
        logging.warning(f"Saved {result.__len__()} Ticketmaster events.")
        self.export_json(result, filepath=save_path("data", data_file))


class TicketmasterGig(Gig):
    genre: str = "Music"
    source: str = "Ticketmaster"


def get_date(event: dict) -> str:
    try:
        return event["dates"]["start"]["dateTime"]
    except Exception:
        return "2099-01-01T00:00:00"


def get_lowest_price(event: dict) -> float:
    prices = event.get("priceRanges")
    if prices is None:
        return 0.0
    try:
        price = min(num.get("min") for num in prices if num.get("min") != 0)
        return float(price) if isinstance(price, (float, str)) else 0.0
    except Exception as exc:
        logging.error(f"Possibly no price for '{event.get('url')}': {exc}.")
        return 0.0


def get_location_info(event: dict) -> tuple[str, ...]:
    try:
        loc = event["_embedded"]["venues"][0]
        venue = loc["name"]
        suburb = loc["city"]["name"]
        state = loc["state"]["stateCode"]
        return venue, suburb, state
    except Exception:
        return "-", "-", "-"


def get_image(event: dict) -> str:
    try:
        return event["images"][0]["url"]
    except Exception:
        return "-"


@timer
@logger(filepath=save_path("data", "app.log"))
def ticketmaster():
    logging.warning(f"Running {os.path.basename(__file__)}")

    destination_cache_file = "ticketmaster_cache.json"
    destination_data_file = "ticketmaster.json"

    scraper = TicketmasterScraper()
    end_page = scraper.end_page
    if end_page is None:
        sys.exit(1)

    events = scraper.get_events(end_page, destination_cache_file)
    if events is None:
        sys.exit(1)

    data = scraper.get_data(events, destination_data_file)


if __name__ == "__main__":
    ticketmaster()
