import logging
import os
from typing import Any

import httpx
import Levenshtein

from strategies.base import FeedItem, FilterStrategy

_logger = logging.getLogger(__name__)

DEFAULT_JEV_ENDPOINT = "https://api.typesafe.ai/v1/systemone"

JEV_DUPLICATE_QUESTIONS = {
    "is_duplicate": {
        "type": "noul",
        "instructions": (
            "Does the Target Article report on the same specific event, announcement, "
            "product release, or news story as any of the Candidate Articles? "
            "Answer True if it is a duplicate, syndication, rehash, or covering the exact "
            "same event. Answer False if it is a distinctly different story, different entity, "
            "or separate development."
        ),
    }
}


class DuplicateFilter(FilterStrategy):
    """URL完全一致、Levenshtein距離、および Jev System One (noul) による重複除外ストラテジー。"""

    def __init__(
        self,
        exist_titles: set[str] | None = None,
        exist_urls: set[str] | None = None,
        similarity_threshold: float = 0.7,
        high_similarity_threshold: float = 0.85,
        candidate_threshold: float = 0.35,
        jev_threshold: float = 0.60,
        api_key: str | None = None,
        endpoint: str | None = None,
        http_client: httpx.Client | None = None,
        enabled_jev: bool = True,
    ) -> None:
        self.exist_titles: set[str] = exist_titles if exist_titles is not None else set()
        self.exist_urls: set[str] = exist_urls if exist_urls is not None else set()
        self.similarity_threshold: float = similarity_threshold
        self.high_similarity_threshold: float = high_similarity_threshold
        self.candidate_threshold: float = candidate_threshold
        self.jev_threshold: float = jev_threshold
        self.enabled_jev: bool = enabled_jev
        self._api_key: str | None = (
            api_key or os.getenv("jev_api_key") or os.getenv("JEV_API_KEY")
        )
        self._endpoint: str = (
            endpoint or os.environ.get("JEV_ENDPOINT") or DEFAULT_JEV_ENDPOINT
        )
        self._http_client = http_client

    def _get_api_key(self) -> str | None:
        if not self._api_key:
            self._api_key = os.getenv("jev_api_key") or os.getenv("JEV_API_KEY")
        return self._api_key.strip() if self._api_key else None

    def _evaluate_with_jev(self, title: str, candidates: list[str]) -> float | None:
        api_key = self._get_api_key()
        if not api_key or not self.enabled_jev:
            return None

        state_text = (
            f"[Target Article]\n"
            f"Title: {title}\n\n"
            f"[Candidate Existing Articles]\n"
            + "\n".join(f"- {c}" for c in candidates)
        )
        payload = {
            "model": "jev-latest",
            "state": state_text,
            "questions": JEV_DUPLICATE_QUESTIONS,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            if self._http_client:
                res = self._http_client.post(self._endpoint, json=payload, headers=headers)
            else:
                with httpx.Client(timeout=10.0) as client:
                    res = client.post(self._endpoint, json=payload, headers=headers)
            res.raise_for_status()
            data = res.json()
            answers: dict[str, Any] = data.get("answers", {})
            noul = answers.get("is_duplicate", {}).get("noul")
            if isinstance(noul, (int, float)):
                _logger.debug("Jev duplicate check for '%s': noul=%.3f", title, noul)
                return float(noul)
        except Exception as e:
            _logger.warning("Jev duplicate evaluation failed, fallback to Levenshtein: %s", e)
        return None

    def check_duplicate(
        self, title: str, url: str
    ) -> tuple[bool, str | None, float | None, str | None]:
        """重複判定を行い、(重複フラグ, 理由, Jev noul値, マッチした候補タイトル) を返す。

        理由:
        - "url": URL完全一致
        - "exact_title": タイトル完全一致
        - "high_similarity": Levenshtein酷似 (>= high_similarity_threshold)
        - "jev": Jev System One による意味的重複 (noul >= jev_threshold)
        - "levenshtein_fallback": Jev未稼働時のLevenshtein閾値超過
        - None: 重複なし
        """
        if url in self.exist_urls:
            return True, "url", None, None
        if not self.exist_titles:
            return False, None, None, None
        if title in self.exist_titles:
            return True, "exact_title", None, title

        scored: list[tuple[float, str]] = []
        for t in self.exist_titles:
            ratio = Levenshtein.ratio(t, title)
            if ratio >= self.high_similarity_threshold:
                return True, "high_similarity", None, t
            if ratio >= self.candidate_threshold:
                scored.append((ratio, t))

        if not scored:
            return False, None, None, None

        scored.sort(key=lambda x: x[0], reverse=True)
        candidates = [t for _, t in scored[:5]]
        top_candidate = candidates[0] if candidates else None

        noul = self._evaluate_with_jev(title, candidates)
        if noul is not None:
            if noul >= self.jev_threshold:
                return True, "jev", noul, top_candidate
            return False, None, noul, top_candidate

        if any(r > self.similarity_threshold for r, _ in scored):
            return True, "levenshtein_fallback", None, top_candidate

        return False, None, None, top_candidate

    def is_duplicate(self, title: str, url: str) -> bool:
        is_dup, reason, noul, top_candidate = self.check_duplicate(title, url)
        if is_dup and reason == "jev":
            _logger.info(
                "[EXCLUDED:duplicate_jev] url=%s, title=%s "
                "(noul=%.2f, threshold=%.2f, candidate=%s)",
                url,
                title,
                noul if noul is not None else 0.0,
                self.jev_threshold,
                top_candidate or "",
            )
        return is_dup

    def filter(self, items: list[FeedItem]) -> list[FeedItem]:
        filtered: list[FeedItem] = []
        for item in items:
            if item.is_excluded:
                continue
            if self.is_duplicate(item.title, item.url):
                item.add_score(1.0, reason="duplicate")
                continue
            self.exist_titles.add(item.title)
            self.exist_urls.add(item.url)
            filtered.append(item)
        return filtered

