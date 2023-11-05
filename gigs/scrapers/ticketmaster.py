import logging
import os
import sys

import httpx
from dotenv import load_dotenv

from gigs.utils import Gig, export_json, logger, save_path, timer


class TicketmasterGig(Gig):
    genre: str = "Music"
    source: str = "Ticketmaster"


def end_page(api_key: str) -> int | None:
    url = f"https://app.ticketmaster.com/discovery/v2/events.json?classificationName=music&countryCode=AU&page=0&apikey={api_key}"  # noqa
    try:
        json = httpx.get(url).json()
        return json["page"]["totalPages"]
    except Exception as exc:
        logging.error(f"Error fetching end page from JSON: {exc}.")
        return None


def get_events(api_key: str, last_page: int) -> list[dict]:
    events = []
    with httpx.Client() as client:
        for page in range(last_page):
            url = f"https://app.ticketmaster.com/discovery/v2/events.json?classificationName=music&countryCode=AU&page={page}&apikey={api_key}"  # noqa
            try:
                json = client.get(url).json()["_embedded"]["events"]
                events.extend(json)
            except Exception as exc:
                logging.error(f"Error fetching JSON '{url}': {exc}.")
    return events


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


def extract_data(events: list[dict]) -> list[dict]:
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
    return result


@timer
@logger(filepath=save_path("data", "app.log"))
def ticketmaster():
    logging.warning(f"Running {os.path.basename(__file__)}")
    load_dotenv()
    api_key = str(os.getenv("TM_KEY"))

    last_page = end_page(api_key)
    if last_page is None:
        sys.exit(1)

    events = get_events(api_key, last_page)
    if not len(events):
        logging.error("No events found!")
        sys.exit(1)
    export_json(events, filepath=save_path("data", "ticketmaster_cache.json"))

    data = extract_data(events)
    logging.warning(f"Found {len(data)} events.")
    export_json(data, filepath=save_path("data", "ticketmaster.json"))


if __name__ == "__main__":
    ticketmaster()
