from tqdm import tqdm

from gigs.scrapers.century import century
from gigs.scrapers.eventbrite import eventbrite
from gigs.scrapers.moshtix import moshtix
# from gigs.scrapers.moshtix_price import moshtix_fetch_price
from gigs.scrapers.moshtix_venue import moshtix_fetch_venue
from gigs.scrapers.oztix import oztix
from gigs.scrapers.phoenix import phoenix
from gigs.scrapers.sydney_opera_house import sydney_opera_house
from gigs.scrapers.ticketek import ticketek
from gigs.scrapers.ticketmaster import ticketmaster


def webscraper():
    bots = [
        century,
        eventbrite,
        oztix,
        phoenix,
        sydney_opera_house,
        ticketek,
        ticketmaster,
        moshtix,
        moshtix_fetch_venue,
    ]

    for bot in tqdm(bots, desc="scrapers", ncols=70):
        bot()


if __name__ == "__main__":
    webscraper()
