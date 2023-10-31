import logging
import os
import re

import httpx
from selectolax.parser import HTMLParser
from gigs.utils import export_json, logger, open_json, save_path, timer, headers


def find_lowest_price(price_list: list[str]) -> float:
    convert_to_floats = list(map(lambda i: float(i.replace("$", "").replace(",", "")), price_list))
    return min(convert_to_floats)


def find_prices(text: str) -> list[str]:
    pattern = r"\$[\d,]+(?:\.\d{2})?"
    return re.findall(pattern, text)


def extract_text(html: HTMLParser, tag: str) -> str:
    tables = html.css(tag)
    return "".join(table.text() for table in tables)


def compile_price(html: HTMLParser) -> float:
    text = extract_text(html=html, tag="table")
    if price_list := find_prices(text):
        return find_lowest_price(price_list)
    else:
        return 0.0


def get_prices_from_events(events: list[dict]):
    result = []
    with httpx.Client(headers=headers) as client:
        for event in events:
            try:
                response = client.get(event["url"])
                tree = HTMLParser(response.text)
                min_price = compile_price(html=tree)
                event["price"] = min_price
                result.append(event)
            except Exception as exc:
                logging.error(f"Error fetching price from URL '{event['url']}': {exc}.")
    return result


@timer
@logger(filepath=save_path("data", "app.log"))
def soh_fetch_price():
    logging.warning(f"Running {os.path.basename(__file__)}")

    fp_json = save_path("data", "sydney_opera_house.json")
    events = open_json(filepath=fp_json)
    data = get_prices_from_events(events)

    export_json(data, filepath=save_path("data", fp_json))


if __name__ == "__main__":
    soh_fetch_price()
