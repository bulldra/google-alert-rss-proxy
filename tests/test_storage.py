from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from storage import StoredFeed, StoredGcs


def test_stored_gcs_not_exists() -> None:
    mock_client = MagicMock()
    mock_blob = MagicMock()
    mock_blob.exists.return_value = False
    mock_client.get_bucket.return_value.blob.return_value = mock_blob

    storage = StoredGcs(
        bucket_name="test-bucket",
        blob_name="feed/test.rss",
        client=mock_client,
    )

    assert storage.is_exists() is False
    assert storage.is_expired() is True
    assert storage.download_as_string() is None


def test_stored_gcs_expired_and_not_expired() -> None:
    mock_client = MagicMock()
    mock_blob = MagicMock()
    mock_blob.exists.return_value = True
    now = datetime.now(timezone.utc)
    mock_client.get_bucket.return_value.blob.return_value = mock_blob

    # TTL内（10分前更新、TTL 30分）
    mock_blob.updated = now - timedelta(minutes=10)
    storage = StoredGcs(
        bucket_name="test-bucket",
        blob_name="feed/test.rss",
        ttl=timedelta(minutes=30),
        client=mock_client,
    )
    assert storage.is_exists() is True
    assert storage.is_expired() is False

    # TTL経過後（40分前更新、TTL 30分）
    mock_blob.updated = now - timedelta(minutes=40)
    storage_expired = StoredGcs(
        bucket_name="test-bucket",
        blob_name="feed/test.rss",
        ttl=timedelta(minutes=30),
        client=mock_client,
    )
    assert storage_expired.is_expired() is True

    # is_refresh=True の場合はTTL内でも expired 判定
    storage_refresh = StoredGcs(
        bucket_name="test-bucket",
        blob_name="feed/test.rss",
        ttl=timedelta(minutes=30),
        is_refresh=True,
        client=mock_client,
    )
    assert storage_refresh.is_expired() is True


def test_stored_feed_get_and_persist() -> None:
    mock_client = MagicMock()
    mock_blob = MagicMock()
    mock_blob.exists.return_value = True
    sample_rss = """<?xml version='1.0' encoding='UTF-8'?>
<rss version="2.0">
  <channel>
    <title>Sample Feed</title>
    <link>https://example.com</link>
    <description>Sample Description</description>
    <item>
      <title>Article 1</title>
      <link>https://example.com/1</link>
    </item>
  </channel>
</rss>"""
    mock_blob.download_as_text.return_value = sample_rss
    mock_client.get_bucket.return_value.blob.return_value = mock_blob

    stored_feed = StoredFeed(
        bucket_name="test-bucket",
        blob_name="feed/test.rss",
        client=mock_client,
    )

    feed_dict = stored_feed.get()
    assert feed_dict is not None
    assert len(feed_dict.entries) == 1
    assert feed_dict.entries[0].title == "Article 1"
    assert stored_feed.get_as_string() == sample_rss

    # persist
    new_rss = "<rss><channel><title>New Feed</title></channel></rss>"
    stored_feed.persist(new_rss)
    mock_blob.upload_from_string.assert_called_with(
        new_rss, content_type="application/rss+xml"
    )

    # parsist alias
    stored_feed.parsist(new_rss)
    assert mock_blob.upload_from_string.call_count == 2
