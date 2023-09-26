import logging
import os
import re

from selectolax.parser import HTMLParser, Node

from gigs.utils import (
    export_json,
    get_request,
    headers,
    logger,
    open_json,
    save_path,
    timer,
)


def clean_text(value: Node) -> float:
    text = value.text().strip()
    if "fees" in text:
        return float(text[1:6])
    new_text = re.sub(pattern=r"[$,\s]+", repl="", string=text)
    return float(new_text)


def get_price(tree: HTMLParser, node: str) -> float:
    prices = tree.css(node)
    if len(prices) == 0:
        return 0.0
    price_list = [clean_text(price) for price in prices]
    return min(price_list)


def extract_price_data(cache_data: list[dict], node: str) -> list[dict]:
    result = []
    for data in cache_data:
        url = data["url"]
        response = get_request(url, headers)
        if response is None:
            logging.error(f"Error fetching response for {url}.")
            continue
        try:
            tree = HTMLParser(response.text)
            data["price"] = get_price(tree, node)
        except Exception as exc:
            logging.error(f"Unable to fetch moshtix price: {exc} -> {data['url']}")
        result.append(data)
    return result


@timer
@logger(filepath=save_path("data", "app.log"))
def moshtix_fetch_price():
    logging.warning(f"Running {os.path.basename(__file__)}")

    NODE_PRICE = "span.col-totalprice.ticket-type-total"

    cache_data = open_json(filepath=save_path("data", "mtix_cache.json"))
    result = extract_price_data(cache_data, NODE_PRICE)
    logging.warning(f"Saved prices for {len(result)} events.")
    export_json(data=result, filepath=save_path("data", "mtix_price.json"))


if __name__ == "__main__":
    moshtix_fetch_price()
