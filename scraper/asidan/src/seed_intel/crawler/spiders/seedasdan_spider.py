from __future__ import annotations

try:
    import scrapy
except ImportError:  # pragma: no cover
    scrapy = None


if scrapy is not None:
    class SeedasdanSpider(scrapy.Spider):
        name = "seedasdan"
        allowed_domains = ["seedasdan.com", "www.seedasdan.com"]
        start_urls = [
            "https://www.seedasdan.com/",
            "https://www.seedasdan.com/en/home-en/",
            "https://www.seedasdan.com/sitemap.xml",
        ]

        def parse(self, response):
            yield {
                "url": response.url,
                "status": response.status,
                "content_type": response.headers.get("Content-Type", b"").decode("utf-8", errors="ignore"),
            }
else:
    SeedasdanSpider = None
