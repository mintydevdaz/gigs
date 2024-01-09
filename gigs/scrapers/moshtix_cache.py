import logging
import os
import sys

import chompjs
import httpx
from selectolax.parser import HTMLParser, Node

from gigs.utils import Gig, WebScraper, custom_headers, export_json, logger, save_path, timer


class MoshtixScraper(WebScraper):
    def __init__(self) -> None:
        super().__init__()
        self.base_url = (
            "https://www.moshtix.com.au/v2/search?query=&CategoryList=2&refine="
        )
        self._headers = custom_headers
        self._page_tag = "section.moduleseparator"
        self._json_tag = "script[type='application/ld+json']"
        self._event_tag = "div.searchresult.clearfix"
        self.end_page = self._get_end_page()
        self.event_nodes = self._get_event_nodes()

    def _extract_page_number(self, response: httpx.Response) -> int | None:
        html = HTMLParser(response.text)
        try:
            pagination_text = html.css_first(self._page_tag).text(strip=True).split(" ")
            page_num = int(pagination_text[-1]) + 1
            logging.warning(f"End page is {page_num}.")
            return page_num
        except Exception as exc:
            logging.error(f"Unable to extract last page: {exc}.")
            return None

    def _get_end_page(self, start_page: int = 1) -> int | None:
        url = f"{self.base_url}{start_page}"
        r = self._get_request(url, self._headers)
        return None if r is None else self._extract_page_number(r)

    def _get_event_nodes(self, start_page: int = 1) -> list[Node] | None:
        end_page = self.end_page
        if end_page is None:
            return None

        # Extract nodes from each page
        result = []
        with httpx.Client(headers=self._headers) as client:
            for page in range(start_page, end_page):
                url = f"{self.base_url}{page}"
                logging.warning(url)
                try:
                    r = client.get(url)
                    html = HTMLParser(r.text)
                    nodes = html.css(self._json_tag)
                    result.extend(nodes)
                except Exception as exc:
                    logging.error(f"Unable to fetch JSON nodes at URL '{url}': {exc}.")
        return result


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
    event_nodes = MoshtixScraper().event_nodes
    if event_nodes is None:
        sys.exit(1)
    data = extract_event_data(event_nodes)

    destination_file = "moshtix_cache.json"
    export_json(data, filepath=save_path("cache", destination_file))


if __name__ == "__main__":
    moshtix_cache()
