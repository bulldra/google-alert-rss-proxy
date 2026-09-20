from datetime import datetime, timedelta, timezone
from typing import Any, cast

from google.cloud import storage  # type: ignore[attr-defined]


class StoredGcs:
    """Google Cloud Storage の blob 操作基底クラス。

    note-followings-feed の実装パターンを踏襲し、TTL判定や文字列取得を提供する。
    """

    def __init__(
        self,
        bucket_name: str,
        blob_name: str,
        ttl: timedelta = timedelta(minutes=30),
        is_refresh: bool = False,
        client: Any | None = None,
    ) -> None:
        storage_client = client if client is not None else storage.Client()
        self._blob = storage_client.get_bucket(bucket_name).blob(blob_name)
        self._current_time: datetime = datetime.now(timezone.utc)
        self._ttl: timedelta = ttl
        self._is_refresh: bool = is_refresh

    def is_exists(self) -> bool:
        return bool(self._blob.exists())

    def is_expired(self) -> bool:
        if self.is_exists() and not self._is_refresh:
            updated = self.get_updated()
            if updated is not None:
                return self._current_time - updated > self._ttl
        return True

    def get_updated(self) -> datetime | None:
        if self.is_exists():
            self._blob.reload()
            return cast(datetime | None, self._blob.updated)
        return None

    def download_as_string(self) -> str | None:
        if self.is_exists():
            content: str = self._blob.download_as_text()
            return content
        return None
