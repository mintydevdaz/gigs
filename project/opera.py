import csv
import itertools
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import requests


def opera():
    # Contruct unique url, get HTML response & parse JSON
    response = get_data(create_url())
    json = get_json(response)

    # # Retrieve event date, title, & url
    dates = []
    bands = []
    urls = []
    for j in json["data"]["tiles"]:
        dates.append(event_date(j))
        bands.append(event_title(j))
        urls.append(event_url(j))

    # Parse date into datetime object. Re-format into string.
    dt = list(map(convert_date, dates))

    # Create venue list
    n = len(dates)
    venue = list(itertools.repeat("Sydney Opera House", n))
    location = list(itertools.repeat("Sydney", n))
    state = list(itertools.repeat("NSW", n))

    # Intialise & update dictionary
    data = {
        "Event_Date": [],
        "Event": [],
        "Venue": [],
        "Location": [],
        "State": [],
        "URL": []
    }

    data["Event_Date"] += dt
    data["Event"] += bands
    data["Venue"] += venue
    data["Location"] += location
    data["State"] += state
    data["URL"] += urls

    save_to_csv(data)


def create_url() -> str:
    """Fetch unique URL containing JSON data.

    URL is constructed from unique Start and End dates. JSON data contains only
    contemporary music events at Sydney Opera House.

    Returns:
        str: Unique URL.
    """
    start_date = str(date.today())
    end_date = str(date.today() + timedelta(days=365))
    return f"https://www.sydneyoperahouse.com/bin/soh/whatsOnFilter?filterPaths=%2Fcontent%2Fsoh%2Fevents%2C%2Fcontent%2Fsoh%2Fevents%2Fwhats-on%2C%2Fcontent%2Fsoh%2Fevents%2Fwhats-on%2Fopera-australia%2F2022%2C%2Fcontent%2Fsoh%2Fevents%2Fwhats-on%2FAntidote%2F2022%2C%2Fcontent%2Fsoh%2Fevents%2Fwhats-on%2Faustralian-chamber-orchestra%2F2022-season&loadMoreNext=14&duration=14&filterType=1&limit=6&offset=0&fromDate={start_date}&toDate={end_date}&genres=event-type%3Acontemporary-music" # noqa


def get_data(url: str) -> requests.models.Response:
    """Fetches a HTML response. Will exit if error occurs.

    Args:
        url (str): Ticketek's Concerts page

    Returns:
        requests.models.Response: HTML response
    """
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
    """Extracts JSON.

    Args:
        response (requests.models.Response): HTML response

    Returns:
        dict: JSON data
    """
    return response.json()


def event_date(json: dict) -> str:
    """Extracts the event's date from JSON.

    Args:
        json (dict): JSON data.

    Returns:
        str: Date of event.
    """
    j = json["schedules"][0].get("performanceDate")
    date = j.split("T")
    return date[0]


def event_title(json: dict) -> str:
    """Extracts name (title) of event.

    Args:
        json (dict): JSON data.

    Returns:
        str: Name of event.
    """
    return json.get("title")


def event_url(json: dict) -> str:
    """Generates URL for individual event.

    Args:
        json (dict): JSON data.

    Returns:
        str: URL of event.
    """
    link = json["description"].get("ctaURL")
    return f"https://www.sydneyoperahouse.com{link}"


def convert_date(date: str) -> str:
    """Converts date into Datetime object and re-formats to desired format.

    Args:
        date (str): Formatted as yyyy-mm-dd (2023-01-01)

    Returns:
        str: Re-formats as dd mmm yyyy (01 Jan 2023)
    """
    parse_dt = datetime.strptime(date, "%Y-%m-%d").date()
    return parse_dt.strftime("%d %b %Y")


def save_to_csv(dict_data: dict) -> csv:
    """Saves dictionary to .csv file.

    Args:
        dict_data (dict): Dictionary of gig data.

    Returns:
        csv: 'opera.csv' saved to folder at Desktop path.
    """
    csv_file = str(Path.home() / "Desktop" / "csv_files" / "opera.csv")
    with open(csv_file, 'w') as f:
        writer = csv.writer(f)
        writer.writerow(dict_data.keys())
        writer.writerows(zip(*dict_data.values()))


if __name__ == "__main__":
    opera()
