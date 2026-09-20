from unittest.mock import MagicMock

import pytest

from strategies import (
    BlacklistTitleFilter,
    BlacklistUrlFilter,
    DuplicateFilter,
    FeedItem,
    GeminiJobFilter,
    GenreFilterStrategy,
)
from strategies.gemini_job import JobExclusionResult


def test_blacklist_url_filter() -> None:
    custom_blacklist = {
        "tlds": ["xyz", "top"],
        "domains": ["spam-domain.com"],
        "patterns": [r"^https?://.*bad-pattern.*$"],
    }
    strategy = BlacklistUrlFilter(custom_blacklist)

    items = [
        FeedItem(title="Good News", url="https://example.com/news/1"),
        FeedItem(title="Bad TLD", url="https://spam.xyz/article/1"),
        FeedItem(title="Bad Domain", url="https://sub.spam-domain.com/post"),
        FeedItem(title="Bad Pattern", url="https://another.com/bad-pattern-test"),
    ]

    filtered = strategy.filter(items)
    assert len(filtered) == 1
    assert filtered[0].title == "Good News"


def test_blacklist_title_filter() -> None:
    custom_blacklist = {
        "title_keywords": ["PR記事", "広告"],
    }
    strategy = BlacklistTitleFilter(custom_blacklist)

    items = [
        FeedItem(title="注目のAI技術トレンド", url="https://example.com/1"),
        FeedItem(title="【PR記事】最新スマホの紹介", url="https://example.com/2"),
        FeedItem(title="最新の広告業界ニュース", url="https://example.com/3"),
        FeedItem(title="", url="https://example.com/4"),
    ]

    filtered = strategy.filter(items)
    assert len(filtered) == 1
    assert filtered[0].title == "注目のAI技術トレンド"


def test_duplicate_filter() -> None:
    strategy = DuplicateFilter(similarity_threshold=0.7)

    items = [
        FeedItem(title="Python 3.12の最新機能解説", url="https://example.com/1"),
        FeedItem(title="Python 3.12の最新機能解説", url="https://example.com/1"),  # URL重複
        FeedItem(
            title="Python 3.12の最新機能解説まとめ",  # 類似度 > 0.7
            url="https://example.com/2",
        ),
        FeedItem(title="Go言語の並行処理入門", url="https://example.com/3"),
    ]

    filtered = strategy.filter(items)
    assert len(filtered) == 2
    assert filtered[0].title == "Python 3.12の最新機能解説"
    assert filtered[1].title == "Go言語の並行処理入門"


def test_gemini_job_filter_success() -> None:
    items = [
        FeedItem(
            title="【Pythonエンジニア急募】月給60万〜 フルリモート案件",
            url="https://example.com/job1",
            summary="大手Web企業でのバックエンド開発エンジニア募集。実務経験3年以上。",
        ),
        FeedItem(
            title="Google Cloudの新機能リリース発表まとめ",
            url="https://example.com/news1",
            summary="Google Cloudは最新のAIモデルを発表しました。",
        ),
        FeedItem(
            title="転職サイトおすすめランキング2026",
            url="https://example.com/job2",
            summary="未経験からIT業界へ転職するための求人サイト比較。",
        ),
    ]

    # モッククライアントのセットアップ
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.parsed = JobExclusionResult(excluded_indices=[0, 2])
    mock_client.models.generate_content.return_value = mock_response

    strategy = GeminiJobFilter(client=mock_client, model="gemini-3.5-flash-lite")
    filtered = strategy.filter(items)

    assert len(filtered) == 1
    assert filtered[0].title == "Google Cloudの新機能リリース発表まとめ"
    mock_client.models.generate_content.assert_called_once()


def test_gemini_job_filter_disabled() -> None:
    items = [
        FeedItem(title="求人情報", url="https://example.com/1"),
    ]
    mock_client = MagicMock()
    strategy = GeminiJobFilter(client=mock_client, enabled=False)

    filtered = strategy.filter(items)
    assert len(filtered) == 1
    mock_client.models.generate_content.assert_not_called()


def test_gemini_job_filter_fallback_on_error() -> None:
    items = [
        FeedItem(title="テスト記事", url="https://example.com/1"),
    ]
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("API Timeout")

    strategy = GeminiJobFilter(client=mock_client, enabled=True)
    # エラー発生時でも例外を送出せず、フェイルオープン（元アイテムを返す）
    filtered = strategy.filter(items)
    assert len(filtered) == 1
    assert filtered[0].title == "テスト記事"


def test_genre_filter_strategy_jevtest_rules() -> None:
    from strategies.genre_filter import GenreFilterStrategy

    items = [
        FeedItem(
            title="【急募】バックエンドエンジニア（フルリモート）",
            url="https://example.com/job",
            summary="大手Web企業での求人案件です。",
        ),
        FeedItem(
            title="【2026年最新】AIの活用法おすすめ10選！徹底まとめ",
            url="https://example.com/slop",
            summary="AIの活用法をまとめました。AIは便利です。いかがでしたか？",
        ),
        FeedItem(
            title="利用規約およびプライバシーポリシー",
            url="https://example.com/terms",
            summary="当サイトの利用規約です。",
        ),
        FeedItem(
            title="Python 3.14 alphaリリースノート詳解",
            url="https://example.com/tech",
            summary="新機能のJITコンパイラとインタープリタ改善について解説します。",
        ),
        FeedItem(
            title="新クラウドサービス春の割引キャンペーン開始",
            url="https://example.com/promo",
            summary="月額プランが20%オフになる特別キャンペーンを開始しました。",
        ),
    ]

    # Jev API モックレスポンスの作成
    mock_http_client = MagicMock()

    def mock_post(url, json, headers):
        state = json.get("state", "")
        mock_res = MagicMock()
        mock_res.raise_for_status.return_value = None

        if "job" in state:
            answers = {
                "should_publish": {"noul": 0.1},
                "is_ai_slop": {"noul": 0.0},
                "is_thin_or_useless": {"noul": 0.2},
                "feed_priority": {"score": 0.0},
                "feed_category": {"choice": "job_posting"},
            }
        elif "slop" in state:
            answers = {
                "should_publish": {"noul": 0.1},
                "is_ai_slop": {"noul": 0.85},
                "is_thin_or_useless": {"noul": 0.6},
                "feed_priority": {"score": 0.0},
                "feed_category": {"choice": "industry_news"},
            }
        elif "terms" in state:
            answers = {
                "should_publish": {"noul": 0.0},
                "is_ai_slop": {"noul": 0.0},
                "is_thin_or_useless": {"noul": 0.5},
                "feed_priority": {"score": 0.0},
                "feed_category": {"choice": "site_utility"},
            }
        elif "tech" in state:
            answers = {
                "should_publish": {"noul": 0.9},
                "is_ai_slop": {"noul": 0.05},
                "is_thin_or_useless": {"noul": 0.05},
                "feed_priority": {"score": 2.0},
                "feed_category": {"choice": "tech_guide"},
            }
        else:  # promo
            answers = {
                "should_publish": {"noul": 0.6},
                "is_ai_slop": {"noul": 0.1},
                "is_thin_or_useless": {"noul": 0.1},
                "feed_priority": {"score": 1.0},
                "feed_category": {"choice": "promo_marketing"},
            }
        mock_res.json.return_value = {"answers": answers}
        return mock_res

    mock_http_client.post.side_effect = mock_post

    strategy = GenreFilterStrategy(api_key="test_key", http_client=mock_http_client)
    filtered = strategy.filter(items)

    assert len(filtered) == 2
    titles = [item.title for item in filtered]
    assert "Python 3.14 alphaリリースノート詳解" in titles
    assert "新クラウドサービス春の割引キャンペーン開始" in titles

    # 除外されたアイテムの状態チェック（スコア蓄積と理由）
    assert items[0].is_excluded is True
    assert items[0].exclude_reason == "job_posting"
    assert items[1].is_excluded is True
    assert items[1].exclude_reason == "ai_slop"
    assert items[2].is_excluded is True
    assert items[2].exclude_reason == "site_utility"


def test_score_accumulation_and_early_exit_pipeline() -> None:
    from strategies.genre_filter import GenreFilterStrategy

    # 1. URLブラックリスト
    url_filter = BlacklistUrlFilter({"tlds": ["xyz"], "domains": [], "patterns": []})
    # 2. タイトルブラックリスト
    title_filter = BlacklistTitleFilter({"title_keywords": ["NGワード"]})
    # 3. 重複判定
    duplicate_filter = DuplicateFilter(similarity_threshold=0.7)
    # 4. ジャンル判定 (モック)
    mock_http_client = MagicMock()
    mock_res = MagicMock()
    mock_res.raise_for_status.return_value = None
    mock_res.json.return_value = {
        "answers": {
            "should_publish": {"noul": 0.8},
            "is_ai_slop": {"noul": 0.1},
            "is_thin_or_useless": {"noul": 0.1},
            "feed_priority": {"score": 1.5},
            "feed_category": {"choice": "tech_guide"},
        }
    }
    mock_http_client.post.return_value = mock_res
    genre_filter = GenreFilterStrategy(api_key="test_key", http_client=mock_http_client)

    items = [
        FeedItem(title="スパムTLD記事", url="https://spam.xyz/bad"),
        FeedItem(title="これはNGワードを含む記事", url="https://example.com/title_ng"),
        FeedItem(title="通常の技術記事", url="https://example.com/ok"),
        FeedItem(title="通常の技術記事", url="https://example.com/ok"),  # 重複
    ]

    pipeline = [url_filter, title_filter, duplicate_filter, genre_filter]

    # パイプライン実行（Early Exit）
    for stage in pipeline:
        items = stage.filter(items)

    # 最終的に残るのは "通常の技術記事" 1件のみ
    assert len(items) == 1
    assert items[0].title == "通常の技術記事"

    # Early Exitにより、Jev API呼び出しの対象は1件のみだったことを確認
    assert mock_http_client.post.call_count == 1
    call_args = mock_http_client.post.call_args[1]
    prompt_sent = call_args["json"]["state"]
    assert "スパムTLD記事" not in prompt_sent
    assert "これはNGワードを含む記事" not in prompt_sent
    assert "通常の技術記事" in prompt_sent


def test_exclusion_logging(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    caplog.set_level(logging.INFO)

    url_filter = BlacklistUrlFilter({"tlds": ["xyz"], "domains": [], "patterns": []})
    title_filter = BlacklistTitleFilter({"title_keywords": ["NGワード"]})
    duplicate_filter = DuplicateFilter(similarity_threshold=0.7)

    items = [
        FeedItem(title="スパムTLD記事", url="https://spam.xyz/bad"),
        FeedItem(title="これはNGワードを含む記事", url="https://example.com/title_ng"),
        FeedItem(title="通常の技術記事", url="https://example.com/ok"),
        FeedItem(title="通常の技術記事", url="https://example.com/ok"),  # 重複
    ]

    mock_http_client = MagicMock()
    mock_res = MagicMock()
    mock_res.raise_for_status.return_value = None
    mock_res.json.return_value = {
        "answers": {
            "should_publish": {"noul": 0.8},
            "is_ai_slop": {"noul": 0.05},
            "is_thin_or_useless": {"noul": 0.05},
            "feed_priority": {"score": 1.5},
            "feed_category": {"choice": "tech_guide"},
        }
    }
    mock_http_client.post.return_value = mock_res
    genre_filter = GenreFilterStrategy(api_key="test_key", http_client=mock_http_client)

    for stage in [url_filter, title_filter, duplicate_filter, genre_filter]:
        items = stage.filter(items)

    # ログ出力内容を検証
    log_records = [rec.message for rec in caplog.records if rec.levelno == logging.INFO]
    log_text = "\n".join(log_records)

    # 除外されたアイテムのみログに出力される（duplicate はログ対象外）
    assert "[EXCLUDED:blacklist_url] url=https://spam.xyz/bad" in log_text
    assert "[EXCLUDED:blacklist_title] url=https://example.com/title_ng" in log_text
    assert "[EXCLUDED:duplicate]" not in log_text
    # 採用されたアイテムはログに出力されない
    assert "PASSED" not in log_text
    assert "[EXCLUDED" in log_text




