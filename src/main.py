import logging

import flask
import functions_framework
import google.cloud.logging

from google_alert_feed import GoogleAlertsFeed

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
        return flask.render_template("/index.html")

    url: str | None = request.args.get("feed")
    if url is None:
        return flask.render_template("/index.html")
    is_refresh: bool = request.args.get("refresh", "").lower() in ["true", "1", "yes"]
    logger.debug("feed: %s (refresh=%s)", url, is_refresh)

    feed: GoogleAlertsFeed = GoogleAlertsFeed()
    if feed.is_valid_url(url) is False:
        return (f"{url} is Invalid URL", 400)
    return flask.Response(
        feed.simplification(url, is_refresh=is_refresh),
        200,
        mimetype="application/rss+xml",
    )
