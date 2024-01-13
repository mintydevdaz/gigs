from tqdm import tqdm

from gigs.scrapers.century import century
from gigs.scrapers.eventbrite import eventbrite
from gigs.scrapers.moshtix_cache import moshtix_cache
from gigs.scrapers.moshtix_parse import moshtix_parse
from gigs.scrapers.oztix import oztix
from gigs.scrapers.phoenix import phoenix
from gigs.scrapers.sydney_opera_house import sydney_opera_house
from gigs.scrapers.sydney_opera_house_price import soh_fetch_price
from gigs.scrapers.ticketek import ticketek
from gigs.scrapers.ticketmaster import ticketmaster


def webscraper():
    bots = [
        century,
        eventbrite,
        moshtix_cache,
        moshtix_parse,
        oztix,
        phoenix,
        sydney_opera_house,
        soh_fetch_price,
        ticketek,
        ticketmaster,
    ]

    for bot in tqdm(bots, desc="scrapers", ncols=70):
        bot()


if __name__ == "__main__":
    webscraper()
