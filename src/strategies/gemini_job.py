import logging
from typing import Any

from google.genai import types
from pydantic import BaseModel, Field

import conf.models as models
from strategies.base import FeedItem, FilterStrategy
from utils.gemini_client import get_gemini_client

_logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
あなたはGoogleアラートのRSSフィードを整理する高精度なコンテンツフィルターです。
提供された記事一覧（インデックスとタイトル、概要）を分析し、「求人・転職・採用・アルバイト・インターン・案件募集・人材募集」に該当する募集・求人記事を特定してください。

【除外対象の例】
- 転職・就職・採用情報、求人募集、募集要項、求人まとめ
- アルバイト・パート・派遣社員の募集
- フリーランス向け案件・副業募集・業務委託募集
- 転職エージェントや求人サイトの個別求人ページ

【除外しない例（通過させる）】
- 一般的なニュース記事、解説・技術ブログ
- 企業の事業展開、新製品・新サービスのプレスリリース
- 業界動向のレポートや雇用の統計調査・市場分析記事
- 人事制度改革や働き方の解説記事

除外対象と判断した記事のインデックス番号（0始まり）を
excluded_indices のリストに格納して返してください。
除外対象が存在しない場合は空リスト [] を返してください。
"""


class JobExclusionResult(BaseModel):
    excluded_indices: list[int] = Field(
        default_factory=list,
        description="求人・転職・採用・案件募集などの記事に該当するインデックス番号（0始まり）のリスト",
    )


class GeminiJobFilter(FilterStrategy):
    """Vertex AI (gemini-3.5-flash-lite) を用いた求人・募集記事のAI除外ストラテジー。"""

    def __init__(
        self,
        context: dict[str, Any] | None = None,
        model: str | None = None,
        client: Any | None = None,
        enabled: bool = True,
    ) -> None:
        self.enabled: bool = enabled
        self._context = context or {}
        self._model: str = model or models.gemini_mini()
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = get_gemini_client(context=self._context)
        return self._client

    def _build_prompt(self, items: list[FeedItem]) -> str:
        lines: list[str] = ["記事一覧:"]
        for idx, item in enumerate(items):
            summary_snippet = item.summary[:150].strip() if item.summary else "なし"
            lines.append(f"[{idx}] タイトル: {item.title}\n概要: {summary_snippet}\n")
        return "\n".join(lines)

    def filter(self, items: list[FeedItem]) -> list[FeedItem]:
        if not self.enabled or not items:
            return items

        prompt_text = self._build_prompt(items)
        try:
            client = self._get_client()
            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=JobExclusionResult,
                temperature=0.0,
            )
            response = client.models.generate_content(
                model=self._model,
                contents=prompt_text,
                config=config,
            )

            excluded_set: set[int] = set()
            if hasattr(response, "parsed") and isinstance(response.parsed, JobExclusionResult):
                excluded_set = set(response.parsed.excluded_indices)
            elif hasattr(response, "text") and response.text:
                parsed = JobExclusionResult.model_validate_json(response.text)
                excluded_set = set(parsed.excluded_indices)

            valid_excluded = {idx for idx in excluded_set if 0 <= idx < len(items)}
            if valid_excluded:
                _logger.info(
                    "GeminiJobFilter excluded %d item(s): %s",
                    len(valid_excluded),
                    [items[i].title for i in sorted(valid_excluded)],
                )

            return [item for idx, item in enumerate(items) if idx not in valid_excluded]

        except Exception as e:
            _logger.warning("GeminiJobFilter encountered an error, bypassing: %s", e, exc_info=True)
            return items
