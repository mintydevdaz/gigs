import itertools
import sys
from datetime import date, datetime

import pandas as pd
import requests


def opera():
    print("Retrieving data from Sydney Opera House website")
    # Contruct unique url, get HTML response & parse JSON
    r = get_html_response(url=create_url())
    json = get_json(response=r)

    # # Retrieve event date, title, & url
    dates = []
    bands = []
    urls = []
    for j in json["data"]["tiles"]:
        dates.append(event_date(j))
        bands.append(event_title(j))
        urls.append(event_url(j))

    # Parse date into datetime object. Re-format into string.
    dt = convert_datetime(dates)

    # Create venue list
    venues = list(itertools.repeat("Sydney Opera House", len(dates)))

    # Intialise & update dictionary
    data = {"Event_Date": [], "Band": [], "Venue": [], "URL": []}
    data["Event_Date"] += dt
    data["Band"] += bands
    data["Venue"] += venues
    data["URL"] += urls

    return table(data)


def create_url() -> str:
    """
    Constructs URL from today's date where the date range spans from today
    +1 year.
    """
    d = date.today()
    next_year = f"{str(d.year + 1)}-{str(d.month)}-{str(d.day)}"
    return f"https://www.sydneyoperahouse.com/bin/soh/whatsOnFilter?filterPaths=%2Fcontent%2Fsoh%2Fevents%2C%2Fcontent%2Fsoh%2Fevents%2Fwhats-on%2C%2Fcontent%2Fsoh%2Fevents%2Fwhats-on%2Fopera-australia%2F2022%2C%2Fcontent%2Fsoh%2Fevents%2Fwhats-on%2FAntidote%2F2022%2C%2Fcontent%2Fsoh%2Fevents%2Fwhats-on%2Faustralian-chamber-orchestra%2F2022-season&loadMoreNext=14&duration=14&filterType=1&limit=6&offset=0&fromDate={str(d)}&toDate={next_year}&genres=event-type%3Acontemporary-music" # noqa


def get_html_response(url: str) -> requests.models.Response:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36" # noqa
        }
        r = requests.get(url, headers=headers, timeout=5)
        r.raise_for_status()
    except requests.exceptions.HTTPError as http_err:
        sys.exit(f"HTTP error occurred: \n'{http_err}'")
    except requests.exceptions.Timeout as timeout_err:
        sys.exit(f"Timeout error occurred: \n'{timeout_err}'")
    except Exception as err:
        sys.exit(f"Error occurred: \n'{err}'")
    return r


def get_json(response: requests.models.Response) -> dict:
    return response.json()


def event_date(json: dict) -> str:
    j = json["schedules"][0].get("performanceDate")
    date, time = j.split("T")
    return date


def event_title(json: dict) -> str:
    return json.get("title")


def event_url(json: dict) -> str:
    """Extracts & builds the event's url"""
    link = json["description"].get("ctaURL")
    return f"https://www.sydneyoperahouse.com{link}"


def convert_datetime(dates: list[str]) -> list[datetime]:
    res = []
    for d in dates:
        i = datetime.strptime(d, "%Y-%m-%d").date()
        res.append(i)
    return res


def table(dict_data: dict) -> pd.DataFrame:
    return pd.DataFrame(dict_data)


if __name__ == "__main__":
    opera()
