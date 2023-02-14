import scrapy
from itemloaders.processors import MapCompose, TakeFirst
from scrapy.crawler import CrawlerProcess
from scrapy.loader import ItemLoader
from w3lib.html import remove_tags


def title_case(value):
    return value.title()


def remove_sydney(value):
    return value.replace("Sydney", "").replace(",", "").strip()


def mosh_suburb(value):
    '''Extracts suburb from venue's address'''
    i = value.split(",")[-1].split()
    return " ".join(i[:-2])


def mosh_state(value):
    '''Extracts State from venue's address'''
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


class PhoenixItem(scrapy.Item):
    Event_Date = scrapy.Field(output_processor=TakeFirst())
    Event = scrapy.Field(input_processor=MapCompose(remove_tags, title_case), output_processor=TakeFirst())
    Venue = scrapy.Field(output_processor=TakeFirst())
    Location = scrapy.Field(output_processor=TakeFirst())
    State = scrapy.Field(output_processor=TakeFirst())
    URL = scrapy.Field(output_processor=TakeFirst())


class MoshtixItem(scrapy.Item):
    Event_Date = scrapy.Field(input_processor=MapCompose(remove_tags, clean_date), output_processor=TakeFirst())
    Event = scrapy.Field(input_processor=MapCompose(remove_tags, remove_space), output_processor=TakeFirst())
    Venue = scrapy.Field(input_processor=MapCompose(remove_tags, remove_sydney, title_case), output_processor=TakeFirst())
    Location = scrapy.Field(input_processor=MapCompose(mosh_suburb), output_processor=TakeFirst())
    State = scrapy.Field(input_processor=MapCompose(mosh_state), output_processor=TakeFirst())
    URL = scrapy.Field(output_processor=TakeFirst())


class CenturyItem(scrapy.Item):
    Event_Date = scrapy.Field(input_processor=MapCompose(remove_tags, century_date), output_processor=TakeFirst())
    Event = scrapy.Field(input_processor=MapCompose(remove_tags), output_processor=TakeFirst())
    Venue = scrapy.Field(input_processor=MapCompose(remove_tags, title_case), output_processor=TakeFirst())
    Location = scrapy.Field(output_processor=TakeFirst())
    State = scrapy.Field(output_processor=TakeFirst())
    URL = scrapy.Field(output_processor=TakeFirst())


class PhoenixSpider(scrapy.Spider):
    name = "phoenix"
    allowed_domains = ["phoenixcentralpark.com.au"]
    start_urls = ["https://phoenixcentralpark.com.au/season-vii"]

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
    name = "mosh"

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
        venue = response.css('h1.pagearticle::text').get()
        address = response.css('div.page_headtitle.page_headtitle_withleftimage > p > a::text').get()
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
    name = "century"

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
            yield scrapy.Request(url.css('a::attr("href")').get(), callback=self.parse_gig)

    def parse_gig(self, response):
        loader = ItemLoader(item=CenturyItem(), selector=response)
        loader.add_css("Event_Date", "li.session-date")
        loader.add_css("Event", "h1.title")
        loader.add_css("Venue", "h5.session-title.subtitle.hide-for-small-only.show-for-medium-up")
        loader.add_value("Location", "Sydney")
        loader.add_value("State", "NSW")
        loader.add_value("URL", response.url)
        yield loader.load_item()


custom_settings = {
    "AUTOTHROTTLE_ENABLED": True,
    "AUTOTHROTTLE_DEBUG": True,
    "ROBOTSTXT_OBEY": True,
    "FEEDS": {"data.jsonl": {"format": "jsonl", "overwrite": False}},
}


process = CrawlerProcess(settings=custom_settings)
process.crawl(PhoenixSpider)
process.crawl(MoshtixSpider)
process.crawl(CenturySpider)
process.start()
