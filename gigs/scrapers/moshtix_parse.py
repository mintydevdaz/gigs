import logging
import os
import unicodedata

from pydantic import field_validator

from gigs.utils import Gig, export_json, logger, open_json, save_path, timer


class MoshtixGig(Gig):
    source: str = "Moshtix"

    @field_validator("title", "url")
    def remove_accents(cls, v):
        if v != "-":
            text = (
                unicodedata.normalize("NFD", v)
                .encode("ascii", "ignore")
                .decode("utf-8")
            )
            return text.strip()

    @field_validator("suburb")
    def capitalize_text(cls, text):
        if " " in text:
            words = text.split(" ")
            return " ".join(word.capitalize() for word in words)
        return text.capitalize()


def get_location_info(event: dict) -> tuple[str, ...]:
    try:
        venue = event["location"]["name"]
        suburb = event["location"]["address"].get("addressLocality", "-")
        state = event["location"]["address"]["addressRegion"]
        return venue, suburb, state
    except KeyError as err:
        logging.error(f"Error parsing location info '{event['name']}: {err}.'")
        return "-", "-", "-"


def get_price(event: dict) -> float:
    nums = event.get("offers", [])
    if len(nums) == 0:
        return 0.0
    elif len(nums) == 1:
        return float(nums[0].get("price", 0.0))
    else:
        prices = [float(num["price"]) for num in nums]
        return min(prices)


def extract_data(events: list[dict]) -> list[dict]:
    data = []
    for event in events:
        venue, suburb, state = get_location_info(event)
        gig = MoshtixGig(
            date=event.get("startDate", "2099-01-01T00:00:00"),
            title=event.get("name", "-"),
            price=get_price(event),
            venue=venue,
            suburb=suburb,
            state=state,
            url=event.get("url", "-"),
            image=event.get("image", "-"),
        )
        data.append(gig.model_dump())
    return data


@timer
@logger(filepath=save_path("data", "app.log"))
def moshtix_parse():
    logging.warning(f"Running {os.path.basename(__file__)}")

    source_file = "moshtix_cache.json"
    destination_file = "moshtix.json"

    events = open_json(filepath=save_path("cache", source_file))
    data = extract_data(events)
    logging.warning(f"Parsed {len(data)} events.")
    export_json(data, filepath=save_path("data", destination_file))


if __name__ == "__main__":
    moshtix_parse()
