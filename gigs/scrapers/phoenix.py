import logging
import os
import re
import sys
import unicodedata

from pydantic import BaseModel, field_validator
from selectolax.parser import HTMLParser

from gigs.utils import (export_json, get_request, headers, logger, save_path,
                        timer)


class Gig(BaseModel):
    event_date: str
    title: str
    price: float = 0.0
    genre: str = "Contemporary"
    venue: str = "Phoenix Central Park"
    suburb: str = "Chippendale"
    state: str = "NSW"
    url: str
    image: str = "-"
    source: str = "Phoenix Central Park"

    @field_validator("event_date")
    def check_valid_date(cls, v):
        """The Phoenix website may present dates not as expected. If the date is not
        formatted as 'd mmm yyyy' OR 'dd mmm yyyy', then default to sentinel value.
        """
        date_pattern = re.compile(
            r"^\d{1,2}\s(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s\d{4}$"
        )
        if not date_pattern.match(v):
            return "01 Jan 2099"
        elif date_pattern.match(v) and v[1].isspace():
            return f"0{v}"
        else:
            return v

    @field_validator("title")
    def remove_accents(cls, text):
        return (
            unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("utf-8")
        )


def get_season_url(base_url: str) -> str | None:
    """
    Fetches the URL for the current season from the given base URL.

    The function sends an HTTP GET request to the specified `base_url` with the
    provided `headers`. If the response is None, an error message is logged and None is
    returned. Otherwise, it attempts to construct the URL for the current season by
    calling the `extract_homepage_text` function with the response and base URL. If any
    exceptions occur during the process, an error message is logged and None is
    returned.

    Args:
        base_url (str): The base URL to fetch the current season URL from.

    Returns:
        str | None: The URL for the current season, or None if an error occurs.

    Raises:
        Exception: If any error occurs during the fetching process.
    """
    response = get_request(base_url, headers)
    if response is None:
        logging.error(f"Error fetching response for {base_url}.")
        return None
    season_url = extract_homepage_text(response, base_url)
    return None if season_url is None else season_url


def extract_homepage_text(response, base_url) -> str | None:
    """
    Extracts the URL of the season from the homepage text.

    Args:
        response: The HTTP response object containing the homepage text.
        base_url: The base URL of the website.

    Returns:
        str | None: The constructed URL of the season, or None if unable to parse the
        text.

    Raises:
        Exception: If an error occurs while parsing the text.

    Example:
        ```python
        response = httpx.get("https://example.com/homepage")
        base_url = "https://example.com"
        url = extract_homepage_text(response, base_url)
        if url:
            print(f"Season URL: {url}")
        else:
            print("Failed to extract season URL.")
        ```
    """
    try:
        tree = HTMLParser(response.text)
        season = next(
            (
                link.attributes["href"]
                for link in tree.css("div.header-nav-folder-item > a")
                if "season" in link.text().lower()
            ),
            "",
        )
        url = f"{base_url}{season}"
        logging.warning(f"Constructed URL: {url}")
        return url
    except Exception as exc:
        logging.error(f"Unable to parse text on homepage: {exc}")
        return None


def get_event_urls(url: str) -> list[str] | None:
    """
    Executes the process of fetching event URLs from the given URL.

    Args:
        url (str): The URL to fetch the response from.

    Returns:
        list[str] | None: A list of event URLs if successful, or None if there was an
        error fetching the response.

    Example:
        ```python
        get_event_urls("https://example.com")
        ```
    """
    response = get_request(url, headers)
    if not response:
        logging.error(f"Error fetching response for {url}.")
        return None

    tree = HTMLParser(response.text)
    return extract_links(tree)


def extract_links(tree: HTMLParser) -> list[str] | None:
    """
    Extracts links from the given HTMLParser instance.

    Args:
        tree (HTMLParser): The HTMLParser instance representing the parsed HTML.

    Returns:
        list[str] | None: A list of extracted links if successful, or None if no links
        are found.

    Example:
        ```python
        parser = HTMLParser(html)
        extract_links(parser)
        ```
    """
    links = tree.css("a.sqs-block-image-link")
    if not links:
        return None

    result = [
        link.css_first("a").attrs.get("href")
        for link in links
        if link.css_first("a").attrs.get("href") is not None
    ]
    return result or None


def get_event_date(tree: HTMLParser, node: str) -> str:
    """
    Extracts the event date from the given HTMLParser instance and CSS selector.

    Args:
        tree (HTMLParser): The HTMLParser instance representing the parsed HTML.
        node (str): The CSS selector for the date element.

    Returns:
        str: The formatted event date string.

    Example:
        ```python
        parser = HTMLParser(html)
        get_event_date(parser, ".date")
        ```
    """
    html = tree.css(node)
    text = (
        html[0].css_first(node).text()
        if len(html) == 1
        else html[1].css_first(node).text()
    )
    # Output ~ THU 3 August 20236:30pm & 8:15pm
    date = text.split()
    return f"{date[1]} {date[2][:3]} {date[3][:4]}".title()


def get_image(html: HTMLParser) -> str:
    meta_tag = html.css_first("meta[property='og:image']")
    return meta_tag.attrs.get("content", "-")


def fetch_data(urls: list[str]) -> list[dict]:
    result = []
    for url in urls:
        response = get_request(url, headers)
        if response is None:
            logging.error(f"Error fetching response for {url}.")
            continue
        try:
            tree = HTMLParser(response.text)
            gig = Gig(
                event_date=get_event_date(tree, node="p.sqsrte-large"),
                title=tree.css_first("h1").text(),
                url=url,
                image=get_image(tree),
            )
            result.append(gig.model_dump())
        except Exception as exc:
            logging.error(f"Error fetching gig info: {exc} ({url})")
            continue
    return result


@timer
@logger(filepath=save_path("data", "app.log"))
def phoenix():
    logging.warning(f"Running {os.path.basename(__file__)}")

    base_url = "https://phoenixcentralpark.com.au"
    url = get_season_url(base_url)
    if url is None:
        sys.exit(1)

    event_urls = get_event_urls(url)
    if event_urls is None:
        logging.error(f"No events found at {url}.")
        sys.exit(1)

    data = fetch_data(event_urls)
    logging.warning(f"Found {len(data)} events.")
    export_json(data, filepath=save_path("data", "phoenix.json"))


if __name__ == "__main__":
    phoenix()
