import logging
import re
import urllib

import feedparser
import flask
import functions_framework
import google.cloud.logging
from feedgen.feed import FeedGenerator

logging_client: google.cloud.logging.Client = google.cloud.logging.Client()
logging_client.setup_logging()
logger: logging.Logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

app: flask.Flask = flask.Flask(__name__)


def is_valid_url(url: str) -> bool:
    match: re.Match = re.match(
        r"^https://www\.google\.co\.jp/alerts/feeds/\d+/\d+$", url
    )
    return match is not None


def get_canonical_url(url: str) -> str:
    canonical_url: str = url
    url_obj: urllib.parse.ParseResult = urllib.parse.urlparse(canonical_url)
    query_dict: dict = urllib.parse.parse_qs(url_obj.query)
    canonical_url = query_dict["url"][0]
    return canonical_url


def translate(url: str) -> str:
    feed: feedparser.FeedParserDict = feedparser.parse(url)
    fg = FeedGenerator()
    fg.title(feed.feed.title)
    fg.link(href=feed.feed.links[0].href)
    fg.description(feed.feed.title)
    feed.entries.sort(key=lambda x: x.published, reverse=False)
    titles: set[str] = set()
    for entry in feed.entries:
        if entry.title in titles:
            continue
        titles.add(entry.title)
        fe = fg.add_entry()
        fe.title(entry.title)
        fe.link(href=get_canonical_url(entry.link))
        fe.description(entry.content[0].value)
        fe.published(entry.published)
        fe.updated(entry.updated)
    return fg.rss_str(pretty=True).decode("utf-8")


@functions_framework.http
def main(request: flask.Request):
    if request.method != "GET":
        return ("Only GET requests are accepted", 405)
    if request.args.get("url") is None:
        return ("Missing required parameter 'url'", 400)

    url: str = request.args.get("url")
    logger.debug("URL: %s", url)
    if is_valid_url(url) is False:
        return (f"{url} is Invalid URL", 400)
    try:
        res: str = translate(url)
        return flask.Response(res, 200, mimetype="application/rss+xml")
    except feedparser.exceptions as e:
        logger.error("Error while parsing feed: %s", e)
        return ("Error while parsing feed", 500)
