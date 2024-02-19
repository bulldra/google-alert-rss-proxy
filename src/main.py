import logging

import feedparser
import flask
import functions_framework
import google.cloud.logging

import utils

app: flask.Flask = flask.Flask(__name__)


@functions_framework.http
def main(request: flask.Request):
    logging_client: google.cloud.logging.Client = google.cloud.logging.Client()
    logging_client.setup_logging()
    logger: logging.Logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    if request.method == "HEAD":
        logger.debug("HEAD %s", request.url)
        return ("", 200)
    if request.method != "GET":
        return ("Only GET requests are accepted", 405)
    if request.args.get("feed") is None:
        return ("Missing required parameter 'feed'", 400)

    url: str = request.args.get("feed")
    logger.debug("feed: %s", url)
    if utils.is_valid_url(url) is False:
        return (f"{url} is Invalid URL", 400)
    try:
        return flask.Response(utils.translate(url), 200, mimetype="application/rss+xml")
    except feedparser.exceptions as e:
        logger.error("Error while parsing feed: %s", e)
        return ("Error while parsing feed", 500)
