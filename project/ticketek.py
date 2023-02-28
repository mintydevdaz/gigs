import csv
import sys
from pathlib import Path

import bs4
import requests
from bs4 import BeautifulSoup

# TODO: dataclass might be suitable for saving data asdict


def ticketek():

    result = []
    for page_num in range(1, 24):
        print(f"-> Fetching data from page {page_num}")
        url = f"https://premier.ticketek.com.au/shows/genre.aspx?c=2048&page={page_num}"
        response = get_data(url)
        data = parse_data(response)
        events = get_events(data)

        for event in events:

            band = get_event_band(event)
            link = get_event_url(event)

            # Single Venue
            if len(event.findAll('div', class_='contentEventAndDate clearfix')) == 1:
                try:
                    loc = get_event_location(event)
                    date = get_event_date(event)
                    venue = loc[0]
                    location = loc[1]
                    state = loc[2]
                    result.append((date, band, venue, location, state, link))
                except Exception as err:
                    print(f"**{err} for {band}**")
                    continue

            # Multi-Venue (cycle through each contentEventAndDate item)
            else:
                for e in event.findAll('div', class_='contentEventAndDate clearfix'):
                    try:
                        loc = get_event_location(event_data=e)
                        date = get_event_date(e)
                        venue = loc[0]
                        location = loc[1]
                        state = loc[2]
                        result.append((date, band, venue, location, state, link))
                    except Exception as err:
                        print(f"**{err} for {band}**")
                        continue

    save_to_csv(result)


def get_data(url: str) -> requests.models.Response:
    """Fetches a HTML response. Will exit if error occurs.

    Args:
        url (str): Ticketek's Concerts page

    Returns:
        requests.models.Response: HTML response
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"  # noqa
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


def parse_data(response: requests.models.Response) -> bs4.BeautifulSoup:
    """Parse HTML response with Beautiful Soup

    Args:
        response (requests.models.Response): HTML response

    Returns:
        bs4.BeautifulSoup: Parsed HTML data
    """
    return BeautifulSoup(response.text, "lxml")


def get_events(data: bs4.BeautifulSoup) -> bs4.element.ResultSet:
    """Fetches all events listed on webpage

    Args:
        data (bs4.BeautifulSoup): Parsed HTML data

    Returns:
        bs4.element.ResultSet: All concert event wrappers on webpage
    """
    return data.find_all('div', class_='resultModule')


def get_event_band(event_data: bs4.element.Tag) -> str:
    """Get the headline act for event

    Args:
        event_data (bs4.element.Tag): Individual event's parsed data

    Returns:
        str: Event / Band title
    """
    return event_data.find('h6').next.strip()


def get_event_url(event_data: bs4.element.Tag) -> str:
    """Fetch the individual event's URL

    Args:
        event_data (bs4.element.Tag): Event's parsed HTML data

    Returns:
        str: URL
    """
    base = "https://premier.ticketek.com.au"
    href = event_data.find('a').get('href')
    return f"{base}{href}"


def get_event_location(event_data: bs4.element.Tag) -> list[str]:
    """Returns a list of strings with the following indexes:
    0. Venue
    1. Suburb / City
    2. State

    Args:
        event_data (bs4.element.Tag): Event location

    Returns:
        list[str]: Venue, Suburb/City, State
    """
    location = event_data.find('div', class_='contentLocation').next.strip()
    return [i.strip() for i in location.split(",")]


def get_event_date(event_data: bs4.element.Tag) -> str:
    """Extracts event's date. Will re-format to 01-Jan-2099 if date contains "TBC".

    Args:
        event_data (bs4.element.Tag): Event's parsed HTML data

    Returns:
        str: Date formatted as string
    """
    date = event_data.find('div', class_='contentDate').next.strip()
    return "01 Jan 2099" if "TBC" in date.upper() else date[4:15]


def save_to_csv(gig_list: list) -> csv:
    """Converts List of data to .csv file. 

    Args:
        gig_list (list): List of scraped event data

    Returns:
        csv: Saves .csv file to Desktop path
    """
    path = str(Path.home() / "Desktop" / "csv_files")
    with open(f"{path}/ticketek.csv", "w") as f:
        # Write headers to top of file
        writer = csv.writer(f)
        writer.writerow(["Event_Date", "Event", "Venue", "Location", "State", "URL"])
        # Append rows underneath
        for row in gig_list:
            writer.writerow(row)
    print("-> Finished")


if __name__ == "__main__":
    ticketek()
