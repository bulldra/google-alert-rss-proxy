import re
import urllib

import feedparser
import Levenshtein
from feedgen.feed import FeedGenerator


def is_valid_url(url: str) -> bool:
    match: re.Match = re.match(
        r"^https://www\.google\.co\.jp/alerts/feeds/\d+/\d+$", url
    )
    return match is not None


def get_canonical_url(url: str) -> str:
    if url is None or url == "":
        return None
    url_obj: urllib.parse.ParseResult = urllib.parse.urlparse(url)
    query_dict: dict = urllib.parse.parse_qs(url_obj.query)
    if "url" in query_dict and len(query_dict["url"]) > 0:
        return query_dict["url"][0]
    return url


def normalize_title(title: str) -> str:
    for target in [
        r"<.+?>",
        r"</.+?>",
        r" - .+$",
        r" \| .+$",
    ]:
        title = re.sub(target, "", title)
    return title


def is_duplicate(exist_titles: set[str], title) -> bool:
    for t in exist_titles:
        if Levenshtein.ratio(t, title) > 0.7:
            return True
    return False


def translate(url: str) -> str:
    feed: feedparser.FeedParserDict = feedparser.parse(url)
    fg = FeedGenerator()
    fg.title(feed.feed.title)
    fg.link(href=feed.feed.links[0].href)
    fg.description(feed.feed.title)
    feed.entries.sort(key=lambda x: x.published)
    exist_titles: set[str] = set()
    for entry in feed.entries:
        title: str = normalize_title(entry.title)
        if is_duplicate(exist_titles, title):
            continue
        exist_titles.add(title)
        fe = fg.add_entry()
        fe.title(title)
        fe.link(href=get_canonical_url(entry.link))
        fe.description("")
        fe.published(entry.published)
    return fg.rss_str(pretty=True).decode("utf-8")
