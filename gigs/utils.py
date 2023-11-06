import json
import logging
import os
import time

import httpx
from pydantic import BaseModel


class Gig(BaseModel):
    date: str = "2099-01-01T00:00:00"
    title: str = "-"
    price: float = 0.0
    genre: str = "-"
    venue: str = "-"
    suburb: str = "-"
    state: str = "-"
    url: str = "-"
    image: str = "-"
    source: str = "-"


def save_path(sub_dir: str, filename: str) -> str:
    """
    Returns the absolute path of a file located in a subdirectory relative to the
    parent directory of the current working directory.

    The function takes a subdirectory name and a filename as input, and returns the
    absolute path of the file located in the specified subdirectory of the parent
    directory of the current working directory.

    Args:
        sub_dir (str): The name of the subdirectory.
        filename (str): The name of the file.

    Returns:
        str: The absolute path of the file.

    Example:
        ```python
        sub_dir = "data"
        filename = "file.txt"
        path = save_path(sub_dir, filename)
        print(path)  # Output: "/path/to/parent_dir/data/file.txt"
        ```
    """
    current_dir = os.getcwd()
    parent_dir = os.path.dirname(current_dir)
    return os.path.join(parent_dir, sub_dir, filename)


def logger(filepath: str):
    def decorator(func):
        def wrapper():
            logging.basicConfig(
                filename=filepath,
                level=logging.WARNING,
                format="%(asctime)s - %(levelname)s | %(message)s",
                datefmt="%d-%b-%y %H:%M:%S",
            )
            return func()

        return wrapper

    return decorator


custom_headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36"  # noqa
}


def get_request(url: str, headers: dict[str, str]) -> httpx.Response | None:
    """
    Sends a GET request to the specified URL with the provided headers and returns the response.

    Args:
        url (str): The URL to send the GET request to.
        headers (dict): The headers to include in the request.

    Returns:
        httpx.Response | None: The response object if the request is successful, or `None` if an HTTP error occurs.
    """
    try:
        response = httpx.get(url, headers=headers, follow_redirects=True)
        response.raise_for_status()
        return response
    except httpx.HTTPError as exc:
        logging.error(f"Request error occurred for URL '{url}': {exc}.")
        return None


payload = {"options": {"use": 0, "geo": None, "postcode": None}}


def get_post_response(url: str, payload: dict) -> httpx.Response | None:
    try:
        response = httpx.post(url, json=payload)
        response.raise_for_status()
        return response
    except httpx.HTTPError as exc:
        logging.error(f"Request error occurred: {exc}.")
        return None


def open_json(filepath: str):
    with open(filepath, "r") as f:
        data = json.load(f)
    return data


def export_json(data, filepath: str) -> None:
    try:
        with open(filepath, "w") as f:
            json.dump(data, f)
    except Exception as exc:
        logging.error(f"Error downloading JSON: {exc}")
        return None


def timer(func):
    def wrapper():
        start = time.perf_counter()
        func()
        end = time.perf_counter()
        total = end - start
        elapsed_time = f"Elapsed Time: {total:.6f} secs ~ {total / 60:.2f} mins."
        logging.warning(elapsed_time)

    return wrapper
