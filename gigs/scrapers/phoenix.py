import datetime
import logging
import os
import sys
import unicodedata
from datetime import datetime

import httpx
from pydantic import field_validator
from selectolax.parser import HTMLParser

from gigs.utils import Gig, export_json, get_request, headers, logger, save_path, timer

# ! Mon, 30-Oct-2023 ~ Times
# * 1. 8s


class PhoenixGig(Gig):
    venue: str = "Phoenix Central Park"
    suburb: str = "Chippendale"
    state: str = "NSW"
    source: str = "Phoenix Central Park"

    @field_validator("date")
    def check_valid_date(cls, date_str):
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
    split = date_str.split("—")  # an 'em dash', not a hyphen / 1—4 Nov 2023
    new_date = f"{split[0]}{split[1][1:]}"
    return datetime.strptime(new_date, fmt).isoformat()


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


def extract_links(html: HTMLParser) -> list[str] | None:
    """
    Extracts links from the given HTMLParser instance.

    Args:
        html (HTMLParser): The HTMLParser instance representing the parsed HTML.

    Returns:
        list[str] | None: A list of extracted links if successful, or None if no links
        are found.

    Example:
        ```python
        parser = HTMLParser(html)
        extract_links(parser)
        ```
    """
    links = html.css("a.sqs-block-image-link")
    if not links:
        return None

    result = [
        link.css_first("a").attrs.get("href")
        for link in links
        if link.css_first("a").attrs.get("href") is not None
    ]
    return result or None


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


def get_image(html: HTMLParser) -> str:
    meta_tag = html.css_first("meta[property='og:image']")
    return meta_tag.attrs.get("content", "-")


def get_data(urls: list[str], title_tag: str, date_tag: str) -> list[dict]:
    result = []
    with httpx.Client(headers=headers) as client:
        for url in urls:
            try:
                response = client.get(url)
                tree = HTMLParser(response.text)
                gig = PhoenixGig(
                    date=tree.css_first(date_tag).text(),
                    title=tree.css_first(title_tag).text(),
                    url=url,
                    image=get_image(tree),
                )
                result.append(gig.model_dump())
            except Exception as exc:
                logging.error(f"Unable to extract data from URL '{url}': {exc}.")
    return result


@timer
@logger(filepath=save_path("data", "app.log"))
def phoenix():
    logging.warning(f"Running {os.path.basename(__file__)}")

    # CSS Selectors
    TITLE_TAG = "div.sqs-html-content > h3"
    DATE_TAG = "div.sqs-html-content > h4"

    base_url = "https://phoenixcentralpark.com.au"
    url = get_season_url(base_url)
    if url is None:
        sys.exit(1)

    urls = get_event_urls(url)
    if urls is None:
        logging.error(f"No events found at {url}.")
        sys.exit(1)

    data = get_data(urls, TITLE_TAG, DATE_TAG)
    logging.warning(f"Found {len(data)} events.")

    export_json(data, filepath=save_path("data", "phoenix.json"))


if __name__ == "__main__":
    phoenix()
