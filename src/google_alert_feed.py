import re
import urllib

import feedparser
import Levenshtein
from feedgen.feed import FeedGenerator


class GoogleAlertsFeed:
    def __init__(self):
        self._exist_titles: set[str] = set()

    def is_valid_url(self, url: str) -> bool:
        return (
            re.match(r"^https://www\.google\.co\.jp/alerts/feeds/\d+/\d+$", url)
            is not None
        )

    def get_canonical_url(self, url: str) -> str:
        if url is None or url == "":
            return None
        url_obj: urllib.parse.ParseResult = urllib.parse.urlparse(url)
        query_dict: dict = urllib.parse.parse_qs(url_obj.query)
        if "url" in query_dict and len(query_dict["url"]) > 0:
            return query_dict["url"][0]
        return url

    def normalize_title(self, title: str) -> str:
        for target in [
            r"<.+?>",
            r"</.+?>",
            r" - .+$",
            r" \| .+$",
        ]:
            title = re.sub(target, "", title)
        return title

    def is_duplicate(self, title) -> bool:
        for t in self._exist_titles:
            if Levenshtein.ratio(t, title) > 0.7:
                return True
        return False

    def simplification(self, url: str) -> str:
        feed: feedparser.FeedParserDict = feedparser.parse(url)
        fg = FeedGenerator()
        fg.title(feed.feed.title)
        fg.link(href=feed.feed.links[0].href)
        fg.description(feed.feed.title)
        feed.entries.sort(key=lambda x: x.published)
        for entry in feed.entries:
            title: str = self.normalize_title(entry.title)
            if self.is_duplicate(title):
                continue
            self._exist_titles.add(title)
            fe = fg.add_entry()
            fe.title(title)
            fe.link(href=self.get_canonical_url(entry.link))
            fe.published(entry.published)
        return fg.rss_str(pretty=True).decode("utf-8")
