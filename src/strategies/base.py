import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

_logger = logging.getLogger(__name__)


@dataclass
class FeedItem:
    """RSSフィードのエントリを表すデータクラス。"""

    title: str
    url: str
    published: str = ""
    published_parsed: Any = None
    summary: str = ""
    raw_entry: Any = None

    # スコア蓄積型 Early Exit 用フィールド
    exclusion_score: float = 0.0
    is_excluded: bool = False
    exclude_reason: str = "none"
    category: str = "unknown"
    score_details: dict[str, float] = field(default_factory=dict)

    def add_score(self, score: float, reason: str, threshold: float = 1.0) -> None:
        """スコアを加算し、閾値以上になった場合は除外フラグを設定する。"""
        self.exclusion_score += score
        self.score_details[reason] = self.score_details.get(reason, 0.0) + score
        if self.exclusion_score >= threshold and not self.is_excluded:
            self.is_excluded = True
            self.exclude_reason = reason


class FilterStrategy(ABC):
    """RSSフィードの除外・フィルタリングを行うストラテジー基底クラス。"""

    @abstractmethod
    def filter(self, items: list[FeedItem]) -> list[FeedItem]:
        """エントリ一覧を受け取り、除外されずに残ったエントリ一覧を返す。"""
        pass


class ItemFilterStrategy(FilterStrategy):
    """1件ごとに除外判定を行うストラテジーのための便利基底クラス。"""

    @abstractmethod
    def should_exclude(self, item: FeedItem) -> bool:
        """指定したアイテムを除外すべき場合 True を返す。"""
        pass

    @property
    def default_reason(self) -> str:
        return "filter"

    def filter(self, items: list[FeedItem]) -> list[FeedItem]:
        remaining: list[FeedItem] = []
        for item in items:
            if item.is_excluded:
                continue
            if self.should_exclude(item):
                item.add_score(1.0, reason=self.default_reason)
                _logger.info(
                    "[EXCLUDED:%s] url=%s, title=%s",
                    self.default_reason,
                    item.url,
                    item.title,
                )
                continue
            remaining.append(item)
        return remaining


