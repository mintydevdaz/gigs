import scrapy
from scrapy.crawler import CrawlerProcess


def charlotte():
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
            url = response.url
            event = response.css("p.sqsrte-large::text").getall()
            date = event[1] if len(event) > 2 else event[0]
            yield {
                "Event_Date": date[4:],
                "Band": response.css("h1::text").get(),
                "Venue": "Phoenix Central Park",
                "URL": url,
            }

    class MoshtixSpider(scrapy.Spider):
        name = "mosh"
        allowed_domains = ["moshtix.com.au"]
        start_urls = [
            "https://moshtix.com.au/v2/venues/big-top-luna-park-sydney/12",
            "https://www.moshtix.com.au/v2/venues/lazybones-lounge-restaurant-bar/7848",
            "https://www.moshtix.com.au/v2/venues/oxford-art-factory-sydney/867",
            "https://moshtix.com.au/v2/venues/roundhouse-sydney/756",
            "https://www.moshtix.com.au/v2/venues/the-lansdowne-hotel-sydney/4775",
        ]

        def parse(self, response):
            venue = response.css("h1.pagearticle::text").get()
            events = response.css("div.searchresult_content")
            for event in events:
                date = (
                    event.css("h2.main-artist-event-header::text").get().strip()[:-10]
                )
                band = event.css("h2.main-event-header > a > span::text").get().strip()
                url = event.css("h2.main-event-header > a").attrib["href"]
                yield {
                    "Event_Date": date[4:],
                    "Band": band,
                    "Venue": venue,
                    "URL": url,
                }

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
            for item in items:
                url = item.css('a::attr("href")').extract_first()
                yield scrapy.Request(url, callback=self.parse_gig)

        def parse_gig(self, response):
            i = response.css("li.session-date::text").get().split(" ")
            date = f"{i[1]} {i[2][:3]} {i[3]}"
            band = response.css("h1.title::text").get()
            venue = response.css(
                "h5.session-title.subtitle.hide-for-small-only.show-for-medium-up::text"
            ).get()
            url = response.url
            yield {
                "Event_Date": date,
                "Band": band,
                "Venue": venue,
                "URL": url,
            }

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


if __name__ == "__main__":
    charlotte()
