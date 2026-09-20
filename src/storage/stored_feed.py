from datetime import timedelta
from typing import Any

import feedparser

from storage.stored_gcs import StoredGcs


class StoredFeed(StoredGcs):
    """Google Cloud Storage に保存された RSS フィードの管理クラス。

    note-followings-feed の StoredFeed 実装パターンを踏襲。
    """

    def __init__(
        self,
        bucket_name: str,
        blob_name: str,
        ttl: timedelta = timedelta(minutes=30),
        is_refresh: bool = False,
        client: Any | None = None,
    ) -> None:
        super().__init__(
            bucket_name=bucket_name,
            blob_name=blob_name,
            ttl=ttl,
            is_refresh=is_refresh,
            client=client,
        )
        self._feed_dict: feedparser.FeedParserDict | None = None
        self._feed_str: str | None = None

    def get(self) -> feedparser.FeedParserDict | None:
        if self._feed_dict:
            return self._feed_dict
        if self.is_exists():
            self._feed_str = self.download_as_string()
            if self._feed_str:
                self._feed_dict = feedparser.parse(self._feed_str)
            else:
                self._feed_dict = None
        else:
            self._feed_dict = None
        return self._feed_dict

    def get_as_string(self) -> str | None:
        self.get()
        return self._feed_str

    def persist(self, feed_str: str) -> None:
        """RSS フィード XML 文字列を GCS に保存・更新する。"""
        self._blob.upload_from_string(feed_str, content_type="application/rss+xml")
        self._feed_str = feed_str
        self._feed_dict = None  # キャッシュクリアして次回パース可能に

    def parsist(self, feed_str: str) -> None:
        """note-follow-feed の typo との互換性のためのエイリアス。"""
        self.persist(feed_str)
