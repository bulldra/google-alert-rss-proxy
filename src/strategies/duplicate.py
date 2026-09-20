import logging

import Levenshtein

from strategies.base import FeedItem, FilterStrategy

_logger = logging.getLogger(__name__)


class DuplicateFilter(FilterStrategy):
    """URL完全一致およびLevenshtein距離によるタイトル類似度での重複除外ストラテジー。"""

    def __init__(
        self,
        exist_titles: set[str] | None = None,
        exist_urls: set[str] | None = None,
        similarity_threshold: float = 0.7,
    ) -> None:
        self.exist_titles: set[str] = exist_titles if exist_titles is not None else set()
        self.exist_urls: set[str] = exist_urls if exist_urls is not None else set()
        self.similarity_threshold: float = similarity_threshold

    def is_duplicate(self, title: str, url: str) -> bool:
        if url in self.exist_urls:
            return True
        for t in self.exist_titles:
            if Levenshtein.ratio(t, title) > self.similarity_threshold:
                return True
        return False

    def filter(self, items: list[FeedItem]) -> list[FeedItem]:
        filtered: list[FeedItem] = []
        for item in items:
            if item.is_excluded:
                continue
            if self.is_duplicate(item.title, item.url):
                item.add_score(1.0, reason="duplicate")
                _logger.info(
                    "[EXCLUDED:duplicate] url=%s, title=%s",
                    item.url,
                    item.title,
                )
                continue
            self.exist_titles.add(item.title)
            self.exist_urls.add(item.url)
            filtered.append(item)
        return filtered

