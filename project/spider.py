import logging
from datetime import datetime
from pathlib import Path

import scrapy
from itemloaders.processors import MapCompose, TakeFirst
from scrapy.crawler import CrawlerProcess
from scrapy.loader import ItemLoader
from w3lib.html import remove_tags


def spider():
    file_path = str(Path.home() / "Desktop" / "csv_files")

    def title_case(value):
        return value.title()

    def phoenix_date(value):
        v = value[0].split()
        return f"{v[0]} {v[1][:3]} {v[2]}"

    def remove_sydney(value):
        return value.replace("Sydney", "").replace(",", "").strip()

    def mosh_suburb(value):
        """Extracts suburb from venue's address"""
        i = value.split(",")[-1].split()
        return " ".join(i[:-2])

    def mosh_state(value):
        """Extracts State from venue's address"""
        i = value.split(",")[-1].split()
        return i[-2]

    def clean_date(value):
        date = value.split(",")[0]
        return date.strip()[4:]

    def remove_space(value):
        return value.strip()

    def century_date(value):
        i = value.split(" ")
        return f"{i[1]} {i[2][:3]} {i[3]}"

    def format_date(value):  # sourcery skip: remove-unnecessary-else
        if value == "01 Jan 2099":
            return value
        else:
            i = datetime.strptime(value[:10], "%Y-%m-%d")
            return i.strftime("%d %b %Y")

    class PhoenixItem(scrapy.Item):
        Event_Date = scrapy.Field(
            input_processor=phoenix_date, output_processor=TakeFirst()
        )
        Event = scrapy.Field(
            input_processor=MapCompose(remove_tags, title_case),
            output_processor=TakeFirst(),
        )
        Venue = scrapy.Field(output_processor=TakeFirst())
        Location = scrapy.Field(output_processor=TakeFirst())
        State = scrapy.Field(output_processor=TakeFirst())
        URL = scrapy.Field(output_processor=TakeFirst())

    class MoshtixItem(scrapy.Item):
        Event_Date = scrapy.Field(
            input_processor=MapCompose(remove_tags, clean_date),
            output_processor=TakeFirst(),
        )
        Event = scrapy.Field(
            input_processor=MapCompose(remove_tags, remove_space),
            output_processor=TakeFirst(),
        )
        Venue = scrapy.Field(
            input_processor=MapCompose(remove_tags, remove_sydney, title_case),
            output_processor=TakeFirst(),
        )
        Location = scrapy.Field(
            input_processor=MapCompose(mosh_suburb), output_processor=TakeFirst()
        )
        State = scrapy.Field(
            input_processor=MapCompose(mosh_state), output_processor=TakeFirst()
        )
        URL = scrapy.Field(output_processor=TakeFirst())

    class CenturyItem(scrapy.Item):
        Event_Date = scrapy.Field(
            input_processor=MapCompose(remove_tags, century_date),
            output_processor=TakeFirst(),
        )
        Event = scrapy.Field(
            input_processor=MapCompose(remove_tags, title_case),
            output_processor=TakeFirst(),
        )
        Venue = scrapy.Field(
            input_processor=MapCompose(remove_tags, title_case),
            output_processor=TakeFirst(),
        )
        Location = scrapy.Field(
            input_processor=MapCompose(remove_tags), output_processor=TakeFirst()
        )
        State = scrapy.Field(output_processor=TakeFirst())
        URL = scrapy.Field(output_processor=TakeFirst())

    class TicketmasterItem(scrapy.Item):
        Event_Date = scrapy.Field(
            input_processor=MapCompose(format_date), output_processor=TakeFirst()
        )
        Event = scrapy.Field(output_processor=TakeFirst())
        Venue = scrapy.Field(output_processor=TakeFirst())
        Location = scrapy.Field(output_processor=TakeFirst())
        State = scrapy.Field(output_processor=TakeFirst())
        URL = scrapy.Field(output_processor=TakeFirst())

    class PhoenixSpider(scrapy.Spider):
        logging.getLogger().addHandler(logging.StreamHandler())
        name = "phoenix"

        custom_settings = {
            "FEED_URI": f"{file_path}/output1.csv",
            "FEED_FORMAT": "csv",
            "FEED_EXPORT_FIELDS": [
                "Event_Date",
                "Event",
                "Venue",
                "Location",
                "State",
                "URL",
            ],
        }

        def start_requests(self):
            urls = ["https://phoenixcentralpark.com.au/season-vii"]
            for url in urls:
                yield scrapy.Request(url, callback=self.parse)

        def parse(self, response):
            events = response.css("div.sqs-block-content")
            for event in events:
                try:
                    url = event.css("a.sqs-block-image-link").attrib["href"]
                    yield scrapy.Request(url, callback=self.parse_event)
                except Exception:
                    continue

        def parse_event(self, response):
            event = response.css("p.sqsrte-large::text").getall()
            date = event[1] if len(event) > 2 else event[0]

            loader = ItemLoader(item=PhoenixItem(), selector=response)
            loader.add_value("Event_Date", date[4:])
            loader.add_css("Event", "h1")
            loader.add_value("Venue", "Phoenix Central Park")
            loader.add_value("Location", "Chippendale")
            loader.add_value("State", "NSW")
            loader.add_value("URL", response.url)
            yield loader.load_item()

    class MoshtixSpider(scrapy.Spider):
        logging.getLogger().addHandler(logging.StreamHandler())
        name = "mosh"

        custom_settings = {
            "FEED_URI": f"{file_path}/output2.csv",
            "FEED_FORMAT": "csv",
            "FEED_EXPORT_FIELDS": [
                "Event_Date",
                "Event",
                "Venue",
                "Location",
                "State",
                "URL",
            ],
        }

        def start_requests(self):
            urls = [
                "https://moshtix.com.au/v2/venues/big-top-luna-park-sydney/12",
                "https://www.moshtix.com.au/v2/venues/lazybones-lounge-restaurant-bar/7848",
                "https://www.moshtix.com.au/v2/venues/oxford-art-factory-sydney/867",
                "https://moshtix.com.au/v2/venues/roundhouse-sydney/756",
                "https://www.moshtix.com.au/v2/venues/the-lansdowne-hotel-sydney/4775",
            ]
            for url in urls:
                yield scrapy.Request(url, callback=self.parse)

        def parse(self, response):
            venue = response.css("h1.pagearticle::text").get()
            address = response.css(
                "div.page_headtitle.page_headtitle_withleftimage > p > a::text"
            ).get()
            for event in response.css("div.searchresult_content"):
                loader = ItemLoader(item=MoshtixItem(), selector=event)
                loader.add_css("Event_Date", "h2.main-artist-event-header")
                loader.add_css("Event", "h2.main-event-header > a > span")
                loader.add_value("Venue", venue)
                loader.add_value("Location", address)
                loader.add_value("State", address)
                loader.add_css("URL", "h2.main-event-header > a::attr(href)")

                yield loader.load_item()

    class CenturySpider(scrapy.Spider):
        logging.getLogger().addHandler(logging.StreamHandler())
        name = "century"

        custom_settings = {
            "FEED_URI": f"{file_path}/output3.csv",
            "FEED_FORMAT": "csv",
            "FEED_EXPORT_FIELDS": [
                "Event_Date",
                "Event",
                "Venue",
                "Location",
                "State",
                "URL",
            ],
        }

        def start_requests(self):
            urls = [
                "https://www.enmoretheatre.com.au/?s&key=upcoming",
                "https://www.metrotheatre.com.au/?s&key=upcoming",
                "https://www.factorytheatre.com.au/?s&key=upcoming",
                "https://www.theconcourse.com.au/?s&key=upcoming",
                "https://www.manningbar.com/?s&key=upcoming",
            ]
            for url in urls:
                yield scrapy.Request(url, callback=self.parse)

        def parse(self, response):
            container = response.css("div.grid-container.le-card-container")
            items = container.css("div.grid-x > a")
            for url in items:
                yield scrapy.Request(
                    url.css('a::attr("href")').get(), callback=self.parse_gig
                )

        def parse_gig(self, response):
            loader = ItemLoader(item=CenturyItem(), selector=response)
            loader.add_css("Event_Date", "li.session-date")
            loader.add_css("Event", "h1.title")
            loader.add_css(
                "Venue",
                "h5.session-title.subtitle.hide-for-small-only.show-for-medium-up",
            )
            loader.add_value("Location", "Sydney")
            loader.add_value("State", "NSW")
            loader.add_value("URL", response.url)
            yield loader.load_item()

    class TicketmasterSpider(scrapy.Spider):
        logging.getLogger().addHandler(logging.StreamHandler())
        name = "ticketmaster"
        # allowed_domains = ["ticketmaster.com.au"]
        page_num = 0

        custom_settings = {
            "FEED_URI": f"{file_path}/output4.csv",
            "FEED_FORMAT": "csv",
            "FEED_EXPORT_FIELDS": [
                "Event_Date",
                "Event",
                "Venue",
                "Location",
                "State",
                "URL",
            ],
        }

        def start_requests(self):
            urls = [
                "https://www.ticketmaster.com.au/api/search/events/category/10001?page=0"
            ]
            for url in urls:
                yield scrapy.Request(url, callback=self.parse)

        def parse(self, response):
            json = response.json()
            for event in json["events"]:
                loader = ItemLoader(item=TicketmasterItem(), response=response)

                # Replaces None/blank value with placeholder date
                loader.add_value(
                    "Event_Date", event["dateStart"].get("localDate") or "01 Jan 2099"
                )
                loader.add_value("Event", event["title"])
                loader.add_value("Venue", event["venue"].get("name"))
                loader.add_value("Location", event["venue"].get("city"))
                loader.add_value("State", event["venue"].get("state"))
                loader.add_value("URL", response.urljoin(event["url"]))
                yield loader.load_item()

            # Access next 20 urls. Stop if JSON contains no information.
            self.page_num += 1
            total = int(json["total"])
            if total != 0:
                next_page = f"https://www.ticketmaster.com.au/api/search/events/category/10001?page={self.page_num}"  # noqa
                yield response.follow(next_page, callback=self.parse)

    custom_settings = {
        "USER_AGENT": "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_1) AppleWebKit/605.1.15 (KHTML, like Gecko Version/16.1 Safari/605.1.15",  # noqa
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_DEBUG": True,
        "ROBOTSTXT_OBEY": False,
        "LOG_FILE": "error_log.log",
        "LOG_LEVEL": "ERROR",
    }

    process = CrawlerProcess(settings=custom_settings)
    process.crawl(PhoenixSpider)
    process.crawl(MoshtixSpider)
    process.crawl(CenturySpider)
    process.crawl(TicketmasterSpider)
    process.start()


if __name__ == "__main__":
    spider()
