import html
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

    def is_black_list_url(self, url: str) -> bool:
        if url is None:
            return True

        for target_tld in [
            "ar",
            "br",
            "buzz",
            "de",
            "finance",
            "in",
            "np",
            "pl",
            "lv",
            "pa",
            "tg",
        ]:
            if re.match(rf"^https?://.+\.{target_tld}/.*$", url) is not None:
                return True

        for target_domain in [
            "shein.com",
            "lewiscs.com",
            "mercari.com",
            "caitlynong.com",
            "ezison.co.jp",
            "fril.jp",
            "rulez.jp",
            "nilecruisereservationcenter.com",
            "ksolutionsng.com",
            "markplusinc.com",
            "aluminum-shields.com",
            "lasolascafe.net",
            "rentwithfido.com",
            "symkorea.com",
            "doda.jp",
            "paypayfleamarket.yahoo.co.jp",
        ]:
            if re.match(rf"^https?://.*{target_domain}/.*$", url) is not None:
                return True

        for target in [
            r"^https?://diamond\.jp/articles/-/.*$",
            r"^https?://qiita\.com/kabumira/.*$",
        ]:
            if re.match(target, url) is not None:
                return True
        return False

    def normalize_title(self, title: str) -> str:
        for target in [
            r"<.+?>",
            r"</.+?>",
        ]:
            title = re.sub(target, "", title)
        title = html.unescape(title)
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

        feed.entries.sort(key=lambda x: x.published_parsed)
        for entry in feed.entries:
            url: str = self.get_canonical_url(entry.link)
            if self.is_black_list_url(url):
                continue
            title: str = self.normalize_title(entry.title)
            if not title or self.is_duplicate(title):
                continue
            self._exist_titles.add(title)
            fe = fg.add_entry()
            fe.title(title)
            fe.link(href=url)
            fe.published(entry.published)
        return fg.rss_str(pretty=True).decode("utf-8")
