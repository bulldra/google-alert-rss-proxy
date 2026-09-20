import json
import re
from pathlib import Path

from strategies.base import FeedItem, ItemFilterStrategy

DEFAULT_BLACKLIST_PATH = Path(__file__).resolve().parent.parent / "conf" / "blacklist.json"


class BlacklistUrlFilter(ItemFilterStrategy):
    """URLのTLD、ドメイン、正規表現パターンによる除外ストラテジー。"""

    def __init__(self, blacklist: dict[str, list[str]] | None = None) -> None:
        if blacklist is None:
            with open(DEFAULT_BLACKLIST_PATH, encoding="utf-8") as f:
                self._blacklist: dict[str, list[str]] = json.load(f)
        else:
            self._blacklist = blacklist

    def is_black_list_url(self, url: str | None) -> bool:
        if not url:
            return True

        for target_tld in self._blacklist.get("tlds", []):
            if re.match(rf"^https?://.+\.{target_tld}/.*$", url) is not None:
                return True

        for target_domain in self._blacklist.get("domains", []):
            if re.match(rf"^https?://.*{target_domain}/.*$", url) is not None:
                return True

        for target in self._blacklist.get("patterns", []):
            if re.match(target, url) is not None:
                return True
        return False

    @property
    def default_reason(self) -> str:
        return "blacklist_url"

    def should_exclude(self, item: FeedItem) -> bool:
        return self.is_black_list_url(item.url)
