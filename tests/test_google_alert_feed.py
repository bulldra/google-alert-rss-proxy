from unittest.mock import MagicMock

import feedparser
import pytest

from google_alert_feed import GoogleAlertsFeed

FEED_URL_BASE = "https://www.google.co.jp/alerts/feeds/"
FEED_URL = FEED_URL_BASE + "12836160871432447773/18160887076817308335"


def test_valid_url() -> None:
    utils: GoogleAlertsFeed = GoogleAlertsFeed()
    result: bool = utils.is_valid_url(FEED_URL)
    assert result is True


def test_is_black_list_url() -> None:
    utils: GoogleAlertsFeed = GoogleAlertsFeed()

    assert utils.is_black_list_url("https://diamond.jp/articles/-/12345678901234567890") is True
    assert utils.is_black_list_url("https://diamojp/articles/-/12345678901234567890") is False
    assert utils.is_black_list_url("https://expresso222.com.br/list/57_13844_58?kg=dy") is True
    assert utils.is_black_list_url("https://expresso222.com/list/57_13844_58?kg=dy") is False
    assert utils.is_black_list_url("https://qiita.com/kabumira/12345678901234567890") is True
    assert (
        utils.is_black_list_url(
            "https://lewiscs.com/c/%E6%97%A5%E6%9C%AC-%E3"
            "%81%AE-%E3%83%88%E3%83%AC%E3%83%B3%E3%83%89"
        )
        is True
    )
    assert (
        utils.is_black_list_url(
            "https://propertyratings.co.in/c/web-%E3%83%9E"
            "%E3%83%BC%E3%82%B1%E3%83%86%E3%82%A3%E3%83%B3%E3%82%B0-%E3%81%A8-%E3%81%AF"
        )
        is True
    )


def test_simplification() -> None:
    utils: GoogleAlertsFeed = GoogleAlertsFeed()
    result: str | None = utils.simplification(FEED_URL)
    if result is None:
        return
    assert result.startswith("<?xml version='1.0' encoding='UTF-8'?>")
    assert result.endswith("</rss>\n")
    assert "Google アラート" in result


def test_simplification_with_mock_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import datetime, timezone
    from unittest.mock import MagicMock

    now = datetime.now(timezone.utc)

    now_str = now.strftime("%a, %d %b %Y %H:%M:%S GMT")
    now_tuple = now.utctimetuple()

    mock_feed = feedparser.FeedParserDict()
    mock_feed.feed = feedparser.FeedParserDict(
        title="Google アラート - AI",
        links=[feedparser.FeedParserDict(href="https://google.co.jp")],
    )

    entry_valid = MagicMock()
    entry_valid.link = "https://example.com/good-article"
    entry_valid.title = "AIの最新技術トレンド解説"
    entry_valid.summary = "人工知能の動向に関する詳細レポート"
    entry_valid.published = now_str
    entry_valid.published_parsed = now_tuple

    entry_blacklist_url = MagicMock()
    entry_blacklist_url.link = "https://diamond.jp/articles/-/123"
    entry_blacklist_url.title = "ダイヤモンド記事"
    entry_blacklist_url.summary = ""
    entry_blacklist_url.published = now_str
    entry_blacklist_url.published_parsed = now_tuple

    entry_job = MagicMock()
    entry_job.link = "https://example.com/job-opening"
    entry_job.title = "【急募】AIエンジニア採用 年収1000万"
    entry_job.summary = "エンジニアを募集しています。"
    entry_job.published = now_str
    entry_job.published_parsed = now_tuple

    mock_feed.entries = [entry_valid, entry_blacklist_url, entry_job]

    monkeypatch.setattr(feedparser, "parse", lambda _: mock_feed)

    mock_http_client = MagicMock()

    def mock_post(url, json, headers):
        state = json.get("state", "")
        mock_res = MagicMock()
        mock_res.raise_for_status.return_value = None

        if "job-opening" in state or "急募" in state:
            answers = {
                "should_publish": {"noul": 0.1},
                "is_ai_slop": {"noul": 0.0},
                "is_thin_or_useless": {"noul": 0.2},
                "feed_priority": {"score": 0.0},
                "feed_category": {"choice": "job_posting"},
            }
        else:
            answers = {
                "should_publish": {"noul": 0.8},
                "is_ai_slop": {"noul": 0.05},
                "is_thin_or_useless": {"noul": 0.05},
                "feed_priority": {"score": 2.0},
                "feed_category": {"choice": "tech_guide"},
            }
        mock_res.json.return_value = {"answers": answers}
        return mock_res

    mock_http_client.post.side_effect = mock_post

    feed = GoogleAlertsFeed(enable_gemini=True)
    feed._genre_filter._http_client = mock_http_client
    feed._genre_filter._api_key = "test_jev_key"

    result = feed.simplification(FEED_URL, enable_gcs=False)
    assert result is not None
    assert "AIの最新技術トレンド解説" in result
    assert "ダイヤモンド記事" not in result
    assert "【急募】AIエンジニア採用 年収1000万" not in result





def test_get_canonical_url() -> None:
    utils: GoogleAlertsFeed = GoogleAlertsFeed()
    assert utils.get_canonical_url(None) is None
    assert utils.get_canonical_url("") is None
    assert utils.get_canonical_url("https://example.com") == "https://example.com"
    assert (
        utils.get_canonical_url(
            "https://www.google.com/url?rct=j&sa=t&url=https://newspicks.com/news/95\
99747/body/&ct=ga&cd=CAIyHDhhM2JmZTQ3YWU1YjVjMjI6Y28uanA6amE6SlA&usg=AOvVaw3vDIV4RYg\
RtMJOxCK2NtR-"
        )
        == "https://newspicks.com/news/9599747/body/"
    )


def test_is_duplicate() -> None:
    utils: GoogleAlertsFeed = GoogleAlertsFeed()
    utils._exist_titles = {
        "ChatGPTを「業務効率化」にしか使わない人の盲点、新しいフロンティアを切り開くこともできる",
        "面倒なことはChatGPTにやらせよう",
    }
    utils._exits_urls = {
        "https://example.com",
        "https://example.com/2",
    }

    assert utils.is_duplicate(
        "ChatGPTを「業務効率化」にしか使わない人の盲点、新しいフロンティアを切り開くこともできる",
        "https://example.com/4",
    )

    assert utils.is_duplicate(
        "ChatGPTを「業務効率化」にしか使わない人の盲点 新しいフロンティアを切り開くこともできる",
        "https://example.com/4",
    )

    assert utils.is_duplicate(
        "ChatGPTを「業務効率化」にしか使わない人の盲点",
        "https://example.com/4",
    )

    assert not utils.is_duplicate(
        "ChatGPTで業務効率化しよう",
        "https://example.com/4",
    )

    assert utils.is_duplicate(
        "面倒なことはChatGPTにやらせたい",
        "https://example.com/4",
    )

    assert not utils.is_duplicate(
        "全てをChatGPTにやらせたい",
        "https://example.com/4",
    )

    assert utils.is_duplicate(
        "全てをChatGPTにやらせたい",
        "https://example.com/2",
    )


def test_simplification_gcs_cache_hit() -> None:
    from unittest.mock import MagicMock

    cached_rss = "<?xml version='1.0'?><rss><channel><title>Cached</title></channel></rss>"
    mock_stored = MagicMock()
    mock_stored.is_expired.return_value = False
    mock_stored.get_as_string.return_value = cached_rss

    feed = GoogleAlertsFeed(
        stored_feed_factory=lambda **kwargs: mock_stored,
        enable_gemini=False,
    )

    result = feed.simplification(FEED_URL)
    assert result == cached_rss
    mock_stored.persist.assert_not_called()


def test_simplification_gcs_cache_miss_and_duplicate_with_past_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    recent_time = now - timedelta(days=2)
    recent_tuple = recent_time.utctimetuple()

    # 過去キャッシュフィード（2日前: 7日以内なので保持される）
    past_entry = feedparser.FeedParserDict()
    past_entry.title = "AIと社会の未来"
    past_entry.link = "https://example.com/past-ai"
    past_entry.published = recent_time.strftime("%a, %d %b %Y %H:%M:%S GMT")
    past_entry.published_parsed = recent_tuple
    past_entry.summary = "過去のAI記事概要"

    past_dict = feedparser.FeedParserDict()
    past_dict.entries = [past_entry]

    mock_stored = MagicMock()
    mock_stored.is_expired.return_value = True
    mock_stored.get.return_value = past_dict

    # 最新フィード: 過去エントリと類似(0.7超)のタイトル + 新規エントリ
    mock_feed = feedparser.FeedParserDict()
    mock_feed.feed = feedparser.FeedParserDict(
        title="Google アラート",
        links=[feedparser.FeedParserDict(href="https://google.co.jp")],
    )

    # 類似度 > 0.7 のタイトル（除外されるべき）
    duplicate_entry = MagicMock()
    duplicate_entry.link = "https://example.com/new-ai"
    duplicate_entry.title = "AIと社会の未来について"
    duplicate_entry.summary = ""
    duplicate_entry.published = now.strftime("%a, %d %b %Y %H:%M:%S GMT")
    duplicate_entry.published_parsed = now.utctimetuple()

    # 全く新しいエントリ（通過すべき）
    fresh_entry = MagicMock()
    fresh_entry.link = "https://example.com/fresh-topic"
    fresh_entry.title = "全く新しいRustプログラミング入門"
    fresh_entry.summary = ""
    fresh_entry.published = now.strftime("%a, %d %b %Y %H:%M:%S GMT")
    fresh_entry.published_parsed = now.utctimetuple()

    mock_feed.entries = [duplicate_entry, fresh_entry]
    monkeypatch.setattr(feedparser, "parse", lambda _: mock_feed)

    feed = GoogleAlertsFeed(
        stored_feed_factory=lambda **kwargs: mock_stored,
        enable_gemini=False,
    )

    result = feed.simplification(FEED_URL)
    assert result is not None
    # 過去エントリと新規エントリが含まれる
    assert "全く新しいRustプログラミング入門" in result
    assert "AIと社会の未来" in result
    # 類似エントリは除外されている
    assert "AIと社会の未来について" not in result
    # GCS に上書き保存されたこと
    mock_stored.persist.assert_called_once()


def test_simplification_gcs_purges_entries_older_than_7_days(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import datetime, timedelta, timezone
    from unittest.mock import MagicMock

    now = datetime.now(timezone.utc)
    old_time = now - timedelta(days=10)  # 10日前（7日超なので破棄されるべき）
    recent_time = now - timedelta(days=1)  # 1日前（残るべき）

    entry_old = feedparser.FeedParserDict()
    entry_old.title = "10日前の古い記事"
    entry_old.link = "https://example.com/old-10"
    entry_old.published = old_time.strftime("%a, %d %b %Y %H:%M:%S GMT")
    entry_old.published_parsed = old_time.utctimetuple()

    entry_recent = feedparser.FeedParserDict()
    entry_recent.title = "昨日の最新記事"
    entry_recent.link = "https://example.com/recent-1"
    entry_recent.published = recent_time.strftime("%a, %d %b %Y %H:%M:%S GMT")
    entry_recent.published_parsed = recent_time.utctimetuple()

    past_dict = feedparser.FeedParserDict()
    past_dict.entries = [entry_old, entry_recent]

    mock_stored = MagicMock()
    mock_stored.is_expired.return_value = True
    mock_stored.get.return_value = past_dict

    mock_feed = feedparser.FeedParserDict()
    mock_feed.feed = feedparser.FeedParserDict(
        title="Google アラート",
        links=[feedparser.FeedParserDict(href="https://google.co.jp")],
    )
    # 新着は空フィード
    mock_feed.entries = []
    monkeypatch.setattr(feedparser, "parse", lambda _: mock_feed)

    feed = GoogleAlertsFeed(
        stored_feed_factory=lambda **kwargs: mock_stored,
        enable_gemini=False,
    )

    result = feed.simplification(FEED_URL)
    assert result is not None
    # 1日前の記事は残る
    assert "昨日の最新記事" in result
    # 10日前の古い記事は破棄されている
    assert "10日前の古い記事" not in result
    mock_stored.persist.assert_called_once()
