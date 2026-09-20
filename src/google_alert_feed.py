import hashlib
import html
import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, cast
from urllib.parse import ParseResult, parse_qs, urlparse

import dateutil.parser
import feedparser
from feedgen.feed import FeedGenerator

from storage import StoredFeed
from strategies import (
    BlacklistTitleFilter,
    BlacklistUrlFilter,
    DuplicateFilter,
    FeedItem,
    FilterStrategy,
    GenreFilterStrategy,
)

_logger = logging.getLogger(__name__)

BLACKLIST_PATH = Path(__file__).parent / "conf" / "blacklist.json"
GCS_CONFIG_PATH = Path(__file__).parent / "conf" / "gcs_config.json"


class GoogleAlertsFeed:
    def __init__(
        self,
        strategies: list[FilterStrategy] | None = None,
        enable_gemini: bool = True,
        enable_gcs: bool = True,
        context: dict[str, Any] | None = None,
        stored_feed_factory: Callable[..., StoredFeed] | None = None,
    ) -> None:
        self._blacklist: dict[str, list[str]] = self._load_blacklist()
        self._gcs_config: dict[str, Any] = self._load_gcs_config()

        self._enable_gcs: bool = enable_gcs
        self._gcs_bucket_name: str = self._gcs_config["gcs_bucket_name"]
        self._gcs_root_dir: str = self._gcs_config["gcs_root_dir"]
        self._ttl_minutes: int = int(self._gcs_config.get("ttl_minutes", 30))
        self._max_days: int = int(self._gcs_config.get("max_days", 7))
        self._max_feed_count: int = int(self._gcs_config.get("max_feed_count", 100))
        self._stored_feed_factory = stored_feed_factory or StoredFeed

        # スコア蓄積型 Early Exit パイプライン
        # 順序: URLブラックリスト -> タイトルブラックリスト -> 重複判定 -> ジャンルブラックリスト
        self._url_filter = BlacklistUrlFilter(self._blacklist)
        self._title_filter = BlacklistTitleFilter(self._blacklist)
        self._duplicate_filter = DuplicateFilter(similarity_threshold=0.7)
        self._genre_filter = GenreFilterStrategy(context=context, enabled=enable_gemini)
        self._gemini_filter = self._genre_filter

        if strategies is not None:
            self._strategies = strategies
        else:
            self._strategies = [
                self._url_filter,
                self._title_filter,
                self._duplicate_filter,
                self._genre_filter,
            ]


    @property
    def _exist_titles(self) -> set[str]:
        return self._duplicate_filter.exist_titles

    @_exist_titles.setter
    def _exist_titles(self, val: set[str]) -> None:
        self._duplicate_filter.exist_titles = val

    @property
    def _exits_urls(self) -> set[str]:
        return self._duplicate_filter.exist_urls

    @_exits_urls.setter
    def _exits_urls(self, val: set[str]) -> None:
        self._duplicate_filter.exist_urls = val

    @staticmethod
    def _load_blacklist() -> dict[str, list[str]]:
        with open(BLACKLIST_PATH, encoding="utf-8") as f:
            data: dict[str, list[str]] = json.load(f)
        return data

    @staticmethod
    def _load_gcs_config() -> dict[str, Any]:
        config: dict[str, Any] = {
            "gcs_bucket_name": "bulldra-api-storage",
            "gcs_root_dir": "google_alert_feed",
            "ttl_minutes": 30,
            "max_days": 7,
            "max_feed_count": 100,
        }
        if GCS_CONFIG_PATH.exists():
            with open(GCS_CONFIG_PATH, encoding="utf-8") as f:
                file_cfg = json.load(f)
                config.update(file_cfg)
        if os.getenv("GCS_BUCKET_NAME"):
            config["gcs_bucket_name"] = os.environ["GCS_BUCKET_NAME"]
        if os.getenv("GCS_ROOT_DIR"):
            config["gcs_root_dir"] = os.environ["GCS_ROOT_DIR"]
        return config

    @staticmethod
    def get_entry_datetime(item: FeedItem) -> datetime | None:
        """FeedItem の公開日時を UTC datetime オブジェクトとして抽出する。"""
        if item.published_parsed:
            try:
                timestamp = time.mktime(item.published_parsed)
                return datetime.fromtimestamp(timestamp, timezone.utc)
            except Exception:
                pass
        if item.published:
            try:
                dt = dateutil.parser.parse(item.published)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return cast(datetime, dt)
            except Exception:
                pass
        return None

    def get_feed_id(self, url: str) -> str:
        """フィードURLからユニークなフィード識別子を抽出する。"""
        m = re.search(r"alerts/feeds/(\d+)/(\d+)", url)
        if m:
            return f"{m.group(1)}_{m.group(2)}"
        return hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]

    def is_valid_url(self, url: str) -> bool:
        return (
            re.match(
                r"^https?://(?:www\.)?google\.(?:com|co\.jp|[a-z.]{2,})/alerts/feeds/\d+/\d+$",
                url,
            )
            is not None
        )


    def get_canonical_url(self, url: str | None) -> str | None:
        if url is None or url == "":
            return None
        url_obj: ParseResult = urlparse(url)
        query_dict: dict[str, list[str]] = parse_qs(url_obj.query)
        if "url" in query_dict and len(query_dict["url"]) > 0:
            return query_dict["url"][0]
        return url

    def is_black_list_url(self, url: str | None) -> bool:
        return self._url_filter.is_black_list_url(url)

    def is_black_list_title(self, title: str) -> bool:
        return self._title_filter.is_black_list_title(title)

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
        return self._duplicate_filter.is_duplicate(title, url)

    def simplification(
        self,
        url: str,
        is_refresh: bool = False,
        enable_gcs: bool | None = None,
    ) -> str | None:
        use_gcs = self._enable_gcs if enable_gcs is None else enable_gcs
        stored_feed: StoredFeed | None = None
        past_items: list[FeedItem] = []

        if use_gcs:
            try:
                feed_id = self.get_feed_id(url)
                blob_name = f"{self._gcs_root_dir}/feed/{feed_id}.rss"
                stored_feed = self._stored_feed_factory(
                    bucket_name=self._gcs_bucket_name,
                    blob_name=blob_name,
                    ttl=timedelta(minutes=self._ttl_minutes),
                    is_refresh=is_refresh,
                )

                # TTL内で未期限切れならキャッシュを即時返却
                if not is_refresh and not stored_feed.is_expired():
                    cached_str = stored_feed.get_as_string()
                    if cached_str:
                        _logger.debug("Returned cached feed from GCS: %s", blob_name)
                        return cached_str

                # キャッシュ済みエントリを読み込んで過去7日以内のエントリを
                # DuplicateFilter に事前登録
                cached_dict = stored_feed.get()
                if cached_dict is not None and getattr(cached_dict, "entries", None):
                    now = datetime.now(timezone.utc)
                    cutoff = now - timedelta(days=self._max_days)
                    for entry in cached_dict.entries:
                        entry_url = self.get_canonical_url(getattr(entry, "link", None))
                        if not entry_url:
                            continue
                        entry_title = self.normalize_title(getattr(entry, "title", ""))
                        if not entry_title:
                            continue

                        past_item = FeedItem(
                            title=entry_title,
                            url=entry_url,
                            published=getattr(entry, "published", ""),
                            published_parsed=getattr(entry, "published_parsed", None),
                            summary=getattr(entry, "summary", ""),
                            raw_entry=entry,
                        )

                        # 7日より古いエントリは重複判定対象・蓄積対象から破棄
                        item_dt = self.get_entry_datetime(past_item)
                        if item_dt is not None and item_dt < cutoff:
                            continue

                        self._duplicate_filter.exist_urls.add(entry_url)
                        self._duplicate_filter.exist_titles.add(entry_title)
                        past_items.append(past_item)
            except Exception as e:
                _logger.warning("GCS cache operation failed, bypassing GCS: %s", e)
                stored_feed = None

        # 最新フィードを取得
        feed: feedparser.FeedParserDict = feedparser.parse(url)
        if not hasattr(feed.feed, "title") or not feed.feed.get("links"):
            if stored_feed:
                cached_str = stored_feed.get_as_string()
                if cached_str:
                    return cached_str
            return None

        fg = FeedGenerator()
        fg.title(feed.feed.title)
        fg.link(href=feed.feed.links[0].href)
        fg.description(feed.feed.title)

        feed.entries.sort(key=lambda x: x.published_parsed or (0,))

        items: list[FeedItem] = []
        for entry in feed.entries:
            entry_url = self.get_canonical_url(entry.link)
            if not entry_url:
                continue

            title = self.normalize_title(entry.title)
            summary = getattr(entry, "summary", "") or ""
            published = getattr(entry, "published", "")
            published_parsed = getattr(entry, "published_parsed", None)

            items.append(
                FeedItem(
                    title=title,
                    url=entry_url,
                    published=published,
                    published_parsed=published_parsed,
                    summary=summary,
                    raw_entry=entry,
                )
            )

        # スコア蓄積型 Early Exit パイプライン実行（順序: URL -> タイトル -> 重複 -> ジャンル）
        for strategy in self._strategies:
            strategy_name = strategy.__class__.__name__
            before_count = len(items)
            items = strategy.filter(items)
            after_count = len(items)
            if before_count != after_count:
                _logger.info(
                    "%s reduced items from %d to %d",
                    strategy_name,
                    before_count,
                    after_count,
                )
            if not items:
                _logger.info("All items excluded early before remaining stages.")
                break

        # 新規アイテムと過去アイテムをマージ
        all_items = items + past_items
        seen_urls: set[str] = set()
        unique_items: list[FeedItem] = []
        for item in all_items:
            if item.url not in seen_urls:
                seen_urls.add(item.url)
                unique_items.append(item)

        # 過去7日以内のエントリのみを保持（7日超の古いエントリを自然削除）
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=self._max_days)
        valid_items: list[FeedItem] = []
        for item in unique_items:
            dt = self.get_entry_datetime(item)
            if dt is None or dt >= cutoff:
                valid_items.append(item)

        # 日付降順にソートして最大件数に制限
        min_dt = datetime.min.replace(tzinfo=timezone.utc)
        valid_items.sort(
            key=lambda x: self.get_entry_datetime(x) or min_dt,
            reverse=True,
        )
        selected_items = valid_items[: self._max_feed_count]
        # RSS出力用に古い順（昇順）に並べ直す
        selected_items.sort(
            key=lambda x: self.get_entry_datetime(x) or min_dt,
        )

        for item in selected_items:
            fe = fg.add_entry()
            fe.title(item.title)
            fe.link(href=item.url)
            if item.published:
                fe.published(item.published)

        result_bytes: bytes = fg.rss_str(pretty=True)
        result_str: str = result_bytes.decode("utf-8")

        # GCS に永続化
        if stored_feed:
            try:
                stored_feed.persist(result_str)
            except Exception as e:
                _logger.warning("Failed to persist feed to GCS: %s", e)

        return result_str
