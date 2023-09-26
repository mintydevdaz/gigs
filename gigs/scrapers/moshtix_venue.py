import logging
import os

from selectolax.parser import HTMLParser

from gigs.utils import (export_json, get_request, headers, logger, open_json,
                        save_path, timer)


def add_venue_info(data: list[dict], venues: dict) -> tuple[list, list]:
    success = []
    errors = []
    for event in data:
        try:
            event["suburb"] = venues[event["venue"]]["suburb"]
            event["state"] = venues[event["venue"]]["state"]
            success.append(event)
        except Exception:
            errors.append(event)
    return success, errors


def find_venue_url(unknown_venues: set[str]) -> tuple:
    success = []
    errors = []
    base_url = "https://www.moshtix.com.au"
    query = f"{base_url}/v2/search?query="
    for venue_name in unknown_venues:
        url = f"{query}{venue_name.replace(' ', '+')}"
        response = get_request(url, headers)
        if response is None:
            logging.error(f"Error fetching response for {url}.")
            continue
        try:
            tree = HTMLParser(response.text)
            link = tree.css_first("h2.main-artist-event-header > a").attributes["href"]
            venue_url = f"{base_url}{link}"
            success.append((venue_name, venue_url))
        except Exception:
            logging.error(f"Unable to scrape url for: {venue_name}")
            errors.append(venue_name.strip())
    return success, errors


def clean_address(address: str, states: list) -> tuple[str, str]:
    if "," not in address:
        return "-", "-"
    try:
        return extract_suburb_and_state(address, states)
    except Exception:
        return "-", "-"


def extract_suburb_and_state(address, states):
    loc = address.split(",")[-1].strip()
    text = loc.split(" ")
    state = [t for t in text if t in states][0].strip()
    idx = text.index(state)
    suburb = " ".join(text[:idx]).strip()
    return suburb, state


def get_location(valid_search_results: tuple[str, str]) -> list[tuple]:
    result = []
    states = ["ACT", "NSW", "NT", "QLD", "SA", "TAS", "VIC", "WA"]
    NODE_DIV = "div.page_headtitle.page_headtitle_withleftimage > p > a"
    for venue, url in valid_search_results:
        response = get_request(url, headers)
        if response is None:
            logging.error(f"Error fetching response for {url}.")
            continue
        try:
            tree = HTMLParser(response.text)
            address = tree.css_first(NODE_DIV).text().strip().upper()
            suburb, state = clean_address(address, states)
            result.append((venue, suburb, state))
        except Exception as exc:
            logging.error(
                f"Error: {exc}.\nUnable to fetch location for: {venue} ({url})."
            )
    return result


def add_to_json(venues: dict, locations: list[tuple]) -> dict:
    for venue, suburb, state in locations:
        venues[venue] = {"suburb": suburb, "state": state}
    return dict(sorted(venues.items()))


@timer
@logger(filepath=save_path("data", "app.log"))
def moshtix_fetch_venue():
    logging.warning(f"Running {os.path.basename(__file__)}")

    data = open_json(filepath=save_path("data", "mtix_price.json"))
    venues = open_json(filepath=save_path("data", "mtix_venues.json"))
    success1, errors1 = add_venue_info(data, venues)

    if errors1:
        unknown_venues = {error["venue"] for error in errors1}
        valid_results, invalid_results = find_venue_url(unknown_venues)
        locations = get_location(valid_results)
        new_venues_list = add_to_json(venues, locations)
        export_json(
            data=new_venues_list, filepath=save_path("data", "mtix_venues.json")
        )

    # Try and obtain location info for previous errors
    success2, errors2 = add_venue_info(errors1, venues)

    # Merge new errors with old errors. Show in log.
    final_success = success1 + success2

    # Overwrite moshtix.json file with successes.
    export_json(data=final_success, filepath=save_path("data", "moshtix.json"))
    logging.warning(f"Remaining Errors: {errors2}")


if __name__ == "__main__":
    moshtix_fetch_venue()
