import logging
import os
import sys

import chompjs
import httpx
from selectolax.parser import HTMLParser, Node

from gigs.utils import (
    export_json,
    get_request,
    custom_headers,
    logger,
    save_path,
    timer,
)


def get_response_and_parse_html(url: str, headers: dict[str, str]) -> HTMLParser | None:
    response = get_request(url, headers)
    return None if response is None else HTMLParser(response.text)


def get_page_number(html: HTMLParser, tag: str) -> int | None:
    try:
        pagination_text = html.css_first(tag).text(strip=True).split(" ")
        page_num = int(pagination_text[-1]) + 1
        logging.warning(f"End page is {page_num}.")
        return page_num
    except Exception as exc:
        logging.error(f"Unable to extract last page: {exc}.")
        return None


def end_page(
    base_url: str, headers: dict[str, str], tag: str, start_page: int = 1
) -> int | None:
    url = f"{base_url}{start_page}"
    html = get_response_and_parse_html(url, headers)
    return None if html is None else get_page_number(html, tag)


def get_event_nodes(
    base_url: str, headers: dict[str, str], json_tag: str, start_page: int = 1, end_page: int = 2
) -> list[Node]:
    event_nodes = []
    with httpx.Client(headers=headers) as client:
        for page in range(start_page, end_page):
            url = f"{base_url}{page}"
            logging.warning(url)
            try:
                response = client.get(url)
                tree = HTMLParser(response.text)
                nodes = tree.css(json_tag)
                event_nodes.extend(nodes)
            except Exception as exc:
                logging.error(f"Unable to fetch JSON nodes at URL '{url}': {exc}.")
    return event_nodes


def extract_event_data(event_nodes: list[Node]) -> list[dict]:
    data = []
    for node in event_nodes:
        event_dict = chompjs.parse_js_object(node.text())
        data.extend(event_dict)
    return data


@timer
@logger(filepath=save_path("data", "app.log"))
def moshtix_cache():
    logging.warning(f"Running {os.path.basename(__file__)}")

    PAGE_TAG = "section.moduleseparator"
    JSON_TAG = "script[type='application/ld+json']"
    EVENT_TAG = "div.searchresult.clearfix"
    base_url = "https://www.moshtix.com.au/v2/search?query=&CategoryList=2&refine="
    destination_file = "moshtix_cache.json"
    headers = custom_headers

    page_num = end_page(base_url, headers, PAGE_TAG)
    if page_num is None:
        logging.error("Error fetching last page number.")
        sys.exit(1)

    event_nodes = get_event_nodes(base_url, headers, JSON_TAG, end_page=page_num)
    data = extract_event_data(event_nodes)
    logging.warning(f"Found {len(data)} events.")
    export_json(data, filepath=save_path("cache", destination_file))


if __name__ == "__main__":
    moshtix_cache()
