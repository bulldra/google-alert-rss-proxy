import concurrent.futures
import logging
import os
from typing import Any

import httpx

from strategies.base import FeedItem, FilterStrategy

_logger = logging.getLogger(__name__)

DEFAULT_JEV_ENDPOINT = "https://api.typesafe.ai/v1/systemone"

JEV_QUESTIONS = {
    "should_publish": {
        "type": "noul",
        "instructions": (
            "Is this webpage or article worth publishing to an RSS reader feed or "
            "curating for subscribers? "
            "Answer True if it offers substantial knowledge, insightful tech guides, "
            "genuine industry news, new product announcements, sale / deal notifications, "
            "PR marketing updates, or educational depth. "
            "When provided, consider Bookmark Count and RSS Summary as key signals of substance. "
            "Answer False if it is merely a website homepage, login screen, navigation index, "
            "job listing / recruitment announcement, empty placeholder, or low-value SEO copy."
        ),
    },
    "is_ai_slop": {
        "type": "noul",
        "instructions": (
            "Does this content exhibit hallmarks of low-effort AI Slop? "
            "(e.g. generic LLM-generated fluff, formulaic boilerplate phrasing like "
            "'In the ever-evolving landscape' or 'delve into', hollow bullet points, "
            "lack of original human perspective, zero primary data, "
            "or automated synthetic filler)?"
        ),
    },
    "is_promotional_ad": {
        "type": "noul",
        "instructions": (
            "Is this content primarily an advertisement, commercial sales campaign, "
            "product PR pitch, or affiliate-driven curation created for marketing rather "
            "than informing readers?"
        ),
    },
    "is_thin_or_useless": {
        "type": "noul",
        "instructions": (
            "Is this content thin, low-substance, boilerplate, or lacking meaningful depth "
            "or actionable information?"
        ),
    },
    "feed_priority": {
        "type": "score",
        "instructions": "Rate the urgency and substance for an RSS feed reader subscriber.",
        "criteria": [
            (
                "Skip / Noise (Homepage, login, job listing / recruitment, "
                "site utility, empty content)"
            ),
            (

                "Standard Feed (Worth reading, standard news, product announcements, "
                "sales / promotions, regular blog post, updates)"
            ),
            (
                "Must Read / High Priority (Exceptional tutorial, major release, "
                "breakthrough insight, authoritative document)"
            ),
        ],
    },
    "feed_category": {
        "type": "choice",
        "instructions": "Classify the primary format of this content for RSS feed tagging.",
        "criteria": {
            "tech_guide": "Technical tutorial, coding guide, architecture, or API reference",
            "industry_news": "Industry news, major release, or formal announcement",
            "opinion_essay": "Opinion, in-depth analysis, interview, or case study",
            "promo_marketing": "Sales campaign, product promotion, pricing, or commercial showcase",
            "job_posting": (
                "Job listing, hiring notice, recruitment announcement, or career opportunity"
            ),
            "site_utility": "Website homepage, login/auth page, terms of service, or nav index",
        },
    },
    "human_depth": {
        "type": "score",
        "instructions": (
            "Evaluate the presence of authentic human insight, primary experience, "
            "or technical substance."
        ),
        "criteria": [
            "AI Slop / Thin generic fluff / Zero depth",
            "Standard / Mixed overview or curation",
            "High Human Depth / Primary source / Authentic expertise or code",
        ],
    },
}


class GenreFilterStrategy(FilterStrategy):
    """Jev System One API (api.typesafe.ai) を用いた AI Slop & 求人・ジャンル除外ストラテジー。"""

    def __init__(
        self,
        api_key: str | None = None,
        endpoint: str | None = None,
        http_client: httpx.Client | None = None,
        enabled: bool = True,
        slop_threshold: float = 0.60,
        context: dict[str, Any] | None = None,
        model: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.enabled: bool = enabled
        self.slop_threshold: float = slop_threshold
        self._api_key: str | None = (
            api_key or os.getenv("jev_api_key") or os.getenv("JEV_API_KEY")
        )
        self._endpoint: str = (
            endpoint or os.environ.get("JEV_ENDPOINT") or DEFAULT_JEV_ENDPOINT
        )
        self._http_client = http_client

    def _get_api_key(self) -> str:
        if not self._api_key:
            self._api_key = os.getenv("jev_api_key") or os.getenv("JEV_API_KEY")
        if not self._api_key:
            raise ValueError("Jev API Key is missing. Please set JEV_API_KEY or jev_api_key.")
        return self._api_key.strip()

    def _evaluate_single_item(self, item: FeedItem, client: httpx.Client) -> None:
        """単一のFeedItemに対してJev System One APIを呼び出し、除外または採用の判定を行う。"""
        summary_snippet = item.summary[:1000].strip() if item.summary else ""
        text_for_length = f"{item.title} {summary_snippet}".strip()
        char_count = len(text_for_length)

        # RSSメタデータトリアージ用文字数チェック:
        # 通常のWeb本文用(150文字)ではなく、RSSメタデータは4文字未満のみ空・極小として除外
        if char_count < 4:
            item.add_score(1.0, reason="thin_content")
            _logger.info(
                "[EXCLUDED:thin_content] url=%s, title=%s (too short: %d chars < 4)",
                item.url,
                item.title,
                char_count,
            )
            return


        api_key = self._get_api_key()
        state_text = (
            f"[RSS Feed Triage - Comprehensive Metadata & Content]\n"
            f"Title: {item.title}\n"
            f"URL: {item.url}\n"
            f"Meta Description: {summary_snippet}"
        )

        payload = {
            "model": "jev-latest",
            "state": state_text,
            "questions": JEV_QUESTIONS,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        res = client.post(self._endpoint, json=payload, headers=headers)
        res.raise_for_status()
        data = res.json()

        answers: dict[str, Any] = data.get("answers", {})

        publish_noul = answers.get("should_publish", {}).get("noul", 0.5)
        slop_noul = answers.get("is_ai_slop", {}).get("noul", 0.0)
        thin_noul = answers.get("is_thin_or_useless", {}).get("noul", 0.0)
        priority_info = answers.get("feed_priority", {})
        priority_score = priority_info.get("score", 1.0)
        category_info = answers.get("feed_category", {})
        selected_choice = category_info.get("choice", "industry_news")

        ai_slop_pct = round(slop_noul * 100)
        is_ai_slop = (ai_slop_pct >= round(self.slop_threshold * 100))

        # 総合フィードスコア (jevtest 準拠: 0-100%)
        raw_pct = (
            (publish_noul * 0.35)
            + ((priority_score / 2.0) * 0.30)
            + ((1.0 - slop_noul) * 0.20)
            + ((1.0 - thin_noul) * 0.15)
        )
        feed_score_pct = max(0, min(100, round(raw_pct * 100)))

        item.category = selected_choice

        # jevtest 準拠の 5 軸トリアージ判定
        if is_ai_slop:
            item.add_score(1.0, reason="ai_slop")
            _logger.info(
                "[EXCLUDED:ai_slop] url=%s, title=%s (slop=%d%%, score=%d%%, category=%s)",
                item.url,
                item.title,
                ai_slop_pct,
                feed_score_pct,
                selected_choice,
            )
        elif selected_choice == "site_utility":
            item.add_score(1.0, reason="site_utility")
            _logger.info(
                "[EXCLUDED:site_utility] url=%s, title=%s (score=%d%%)",
                item.url,
                item.title,
                feed_score_pct,
            )
        elif selected_choice == "job_posting":
            item.add_score(1.0, reason="job_posting")
            _logger.info(
                "[EXCLUDED:job_posting] url=%s, title=%s (score=%d%%)",
                item.url,
                item.title,
                feed_score_pct,
            )
        elif thin_noul >= 0.75:
            item.add_score(1.0, reason="thin_content")
            _logger.info(
                "[EXCLUDED:thin_content] url=%s, title=%s (thin=%.2f, score=%d%%)",
                item.url,
                item.title,
                thin_noul,
                feed_score_pct,
            )
        elif selected_choice == "promo_marketing" and slop_noul < 0.50:
            # 製品宣伝・セール告知・PRマーケティング主体の記事は除外せず採用（ログ出力なし）
            pass
        elif feed_score_pct >= 45 and slop_noul < 0.50:
            # 必読・通常採用記事（ログ出力なし）
            pass
        else:
            item.add_score(1.0, reason="thin_content")
            _logger.info(
                "[EXCLUDED:thin_content] url=%s, title=%s (score=%d%% < 45%%) [基準未達 除外]",
                item.url,
                item.title,
                feed_score_pct,
            )


    def filter(self, items: list[FeedItem]) -> list[FeedItem]:

        if not self.enabled or not items:
            return [item for item in items if not item.is_excluded]

        # 前段のブラックリストや重複判定ですでに除外されたものはスキップ（Early Exit）
        candidates: list[FeedItem] = [item for item in items if not item.is_excluded]
        if not candidates:
            return []

        # API Key の存在確認（未設定時はフェイルオープン）
        try:
            self._get_api_key()
        except ValueError as e:
            _logger.warning("GenreFilterStrategy bypassing due to missing API key: %s", e)
            return candidates

        client = self._http_client or httpx.Client(timeout=30.0)
        should_close_client = self._http_client is None

        try:
            max_workers = min(5, len(candidates))
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(self._evaluate_single_item, item, client): item
                    for item in candidates
                }
                for future in concurrent.futures.as_completed(futures):
                    target_item = futures[future]
                    try:
                        future.result()
                    except Exception as e:
                        _logger.warning(
                            "Jev evaluation failed for item '%s', passing: %s",
                            target_item.title,
                            e,
                        )

            return [item for item in candidates if not item.is_excluded]

        finally:
            if should_close_client:
                client.close()
