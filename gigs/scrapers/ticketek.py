import logging
import os
import unicodedata

import httpx
from pydantic import BaseModel, field_validator
from selectolax.parser import HTMLParser, Node

from gigs.utils import export_json, logger, save_path, timer


class Gig(BaseModel):
    event_date: str = "-"
    title: str = "-"
    price: float = 0.0
    genre: str = "-"
    venue: str = "-"
    suburb: str = "-"
    state: str = "-"
    url: str = "-"
    image: str = "-"
    source: str = "Ticketek"

    @field_validator("event_date")
    def clean_date(cls, v):
        return f"0{v.title().strip()}" if v[1].isspace() else v.title().strip()

    @field_validator("title")
    def remove_accents(cls, text):
        return (
            unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("utf-8")
        )


def get_request(url: str) -> httpx.Response | None:
    try:
        response = httpx.get(url, follow_redirects=True)
        response.raise_for_status()
        return response
    except httpx.HTTPError as exc:
        logging.error(f"Request error occurred: {exc}.")
        return None


def get_events(base_url: str, node: str, end_page: int) -> list[Node]:
    """
    Fetches events from a given base URL by making HTTP requests to multiple pages.

    Args:
        base_url (str): The base URL to fetch events from.
        node (str): The CSS selector for the desired HTML node containing the events.
        end_page (int): The number of pages to fetch events from.

    Returns:
        list[Node]: A list of nodes containing the fetched events.

    Raises:
        Exception: If there is an error parsing the HTML text.

    Example:
        ```python
        base_url = "https://example.com/events?page="
        node = ".event"
        end_page = 5

        events = get_events(base_url, node, end_page)
        for event in events:
            print(event)
        ```
    """
    result = []
    for page_num in range(1, end_page):
        url = f"{base_url}{page_num}"
        if response := get_request(url):
            try:
                tree = HTMLParser(response.text)
                result.extend(tree.css(node))
            except Exception as exc:
                logging.error(f"Error parsing text for page {page_num} -> {exc}.")
        else:
            logging.error(f"Error fetching response for {url}.")
    return result


def get_url(node: Node) -> str:
    base_url = "https://premier.ticketek.com.au"
    try:
        href = node.css_first("a").attributes["href"]
        return f"{base_url}{href}"
    except Exception:
        return "-"


def get_image(node: Node) -> str:
    try:
        image = node.css_first("img").attributes["src"]
        return f"https:{image}"
    except Exception:
        return "-"


def get_location(event: Node, node_location: str) -> list[str]:
    """
    Extracts location information from an event using a CSS selector. Indices represent
    (0) Venue, (1) City, (2) State.

    Args:
        event (selectolax.parser.Node): The event node to extract location from.
        node_location (str): The CSS selector for the location node.

    Returns:
        list[str]: A list containing the extracted location information.

    Examples:
        ```python
        event = selectolax.parser.Node()
        node_location = ".location"

        location = get_location(event, node_location)
        print(location)  # ['Venue', '-', 'Country']
        ```
    """
    data = event.css_first(node_location).text().strip()
    loc = [i.strip() for i in data.split(",")]
    if len(loc) == 3:
        return loc
    elif len(loc) == 4:
        return [f"{loc[0]}, {loc[1]}", loc[2], loc[3]]
    else:
        return [f"{loc[0]}", "-", f"{loc[-1]}"]


def get_date(event: Node, node_date: str) -> str:
    """
    Retrieves the date from the specified event node.

    Args:
        event (selectolax.parser.Node): The event node.
        node_date (str): The CSS selector for the date element.

    Returns:
        str: The formatted date string. Returns "01 Jan 2099" if "TBC" is found in the
        date string, otherwise returns a substring of the date.

    Example:
        ```python
        event_node = selectolax.parser.Node()
        node_date = ".date"
        date = get_date(event_node, node_date)
        print(date)
        ```
    """
    dt_object = event.css_first(node_date).text().strip()
    return "01 Jan 2099" if "TBC" in dt_object.upper() else dt_object[4:15]


def build_gig(
    event: Node,
    title: str,
    url: str,
    image: str,
    node_location: str,
    node_date: str,
):
    loc = get_location(event, node_location)
    gig = Gig(
        event_date=get_date(event, node_date),
        title=title,
        venue=loc[0],
        suburb=loc[1],
        state=loc[2],
        url=url,
        image=image,
    )
    return gig.model_dump()


def extract_event_data(
    events: list[Node],
    node_venue: str,
    node_location: str,
    node_date: str,
) -> list[dict]:
    """
    Extracts event data from a list of Node objects based on the specified criteria.

    The function iterates over the events and retrieves the title, URL, and image for
    each event. It then builds a list of gigs by calling the 'build_gig' function for
    each show that matches the 'node_venue' criteria. The resulting list of gigs is
    returned.

    Args:
        events (list[Node]): A list of Node objects representing events.
        node_venue (str): The CSS selector for the venue element.
        node_location (str): The CSS selector for the location element.
        node_date (str): The CSS selector for the date element.

    Returns:
        list[dict]: A list of dictionaries representing the extracted event data.

    Example:
        ```python
        events = get_events()
        node_venue = ".venue"
        node_location = ".location"
        node_date = ".date"

        extracted_data = extract_event_data(events, node_venue, node_location,
        node_date)
        print(extracted_data)
        ```
    """
    result = []
    for event in events:
        title = event.css_first("h6").text().strip()
        url = get_url(node=event)
        image = get_image(node=event)

        gigs = [
            build_gig(show, title, url, image, node_location, node_date)
            for show in event.css(node_venue)
        ]
        result.extend(gigs)

    return result


@timer
@logger(filepath=save_path("data", "app.log"))
def ticketek():
    logging.warning(f"Running {os.path.basename(__file__)}")

    BASE_URL = "https://premier.ticketek.com.au/shows/genre.aspx?c=2048&page="
    NODE_EVENT = "div.resultModule"
    NODE_VENUE = "div.contentEventAndDate.clearfix"
    NODE_LOCATION = "div.contentLocation"
    NODE_DATE = "div.contentDate"

    events = get_events(BASE_URL, NODE_EVENT, end_page=24)
    data = extract_event_data(events, NODE_VENUE, NODE_LOCATION, NODE_DATE)
    logging.warning(f"Found {len(data)} events.")
    export_json(data, filepath=save_path("data", "ticketek.json"))


if __name__ == "__main__":
    ticketek()
