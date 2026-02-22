import html
import json
import re
from pathlib import Path
from urllib.parse import ParseResult, parse_qs, urlparse

import feedparser
import Levenshtein
from feedgen.feed import FeedGenerator

BLACKLIST_PATH = Path(__file__).parent / "conf" / "blacklist.json"


class GoogleAlertsFeed:
    def __init__(self) -> None:
        self._exist_titles: set[str] = set()
        self._exits_urls: set[str] = set()
        self._blacklist: dict[str, list[str]] = self._load_blacklist()

    @staticmethod
    def _load_blacklist() -> dict[str, list[str]]:
        with open(BLACKLIST_PATH, encoding="utf-8") as f:
            data: dict[str, list[str]] = json.load(f)
        return data

    def is_valid_url(self, url: str) -> bool:
        return re.match(r"^https://www\.google\.co\.jp/alerts/feeds/\d+/\d+$", url) is not None

    def get_canonical_url(self, url: str | None) -> str | None:
        if url is None or url == "":
            return None
        url_obj: ParseResult = urlparse(url)
        query_dict: dict[str, list[str]] = parse_qs(url_obj.query)
        if "url" in query_dict and len(query_dict["url"]) > 0:
            return query_dict["url"][0]
        return url

    def is_black_list_url(self, url: str | None) -> bool:
        if url is None:
            return True

        for target_tld in self._blacklist["tlds"]:
            if re.match(rf"^https?://.+\.{target_tld}/.*$", url) is not None:
                return True

        for target_domain in self._blacklist["domains"]:
            if re.match(rf"^https?://.*{target_domain}/.*$", url) is not None:
                return True

        for target in self._blacklist["patterns"]:
            if re.match(target, url) is not None:
                return True
        return False

    def is_black_list_title(self, title: str) -> bool:
        for keyword in self._blacklist.get("title_keywords", []):
            if keyword in title:
                return True
        return False

    def normalize_title(self, title: str) -> str:
        for target in [
            r"<.+?>",
            r"</.+?>",
            r" ...$",
        ]:
            title = re.sub(target, "", title)
        title = html.unescape(title)
        return title

    def is_duplicate(self, title: str, url: str) -> bool:
        for t in self._exits_urls:
            if t == url:
                return True
        for t in self._exist_titles:
            if Levenshtein.ratio(t, title) > 0.7:
                return True
        return False

    def simplification(self, url: str) -> str | None:
        feed: feedparser.FeedParserDict = feedparser.parse(url)
        if not hasattr(feed.feed, "title") or not feed.feed.get("links"):
            return None
        fg = FeedGenerator()
        fg.title(feed.feed.title)
        fg.link(href=feed.feed.links[0].href)
        fg.description(feed.feed.title)

        feed.entries.sort(key=lambda x: x.published_parsed)
        for entry in feed.entries:
            entry_url: str | None = self.get_canonical_url(entry.link)
            if self.is_black_list_url(entry_url):
                continue
            assert entry_url is not None

            title: str = self.normalize_title(entry.title)
            if not title or self.is_black_list_title(title) or self.is_duplicate(title, entry_url):
                continue
            self._exist_titles.add(title)
            self._exits_urls.add(entry_url)

            fe = fg.add_entry()
            fe.title(title)
            fe.link(href=entry_url)
            fe.published(entry.published)
        result: bytes = fg.rss_str(pretty=True)
        return result.decode("utf-8")
