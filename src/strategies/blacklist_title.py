import json
from pathlib import Path

from strategies.base import FeedItem, ItemFilterStrategy

DEFAULT_BLACKLIST_PATH = Path(__file__).resolve().parent.parent / "conf" / "blacklist.json"


class BlacklistTitleFilter(ItemFilterStrategy):
    """タイトル内のNGキーワードによる除外ストラテジー。"""

    def __init__(self, blacklist: dict[str, list[str]] | None = None) -> None:
        if blacklist is None:
            with open(DEFAULT_BLACKLIST_PATH, encoding="utf-8") as f:
                self._blacklist: dict[str, list[str]] = json.load(f)
        else:
            self._blacklist = blacklist

    def is_black_list_title(self, title: str) -> bool:
        if not title:
            return True

        for keyword in self._blacklist.get("title_keywords", []):
            if keyword in title:
                return True
        return False

    @property
    def default_reason(self) -> str:
        return "blacklist_title"

    def should_exclude(self, item: FeedItem) -> bool:
        return self.is_black_list_title(item.title)
