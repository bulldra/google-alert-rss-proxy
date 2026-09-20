import json
from functools import lru_cache
from pathlib import Path
from typing import Any, cast


@lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    path = Path(__file__).resolve().parent / "models.json"
    with open(path, encoding="utf-8") as f:
        return cast(dict[str, Any], json.load(f))


def gemini_standard() -> str:
    data = _load()
    if "gemini" in data and "standard" in data["gemini"]:
        return str(data["gemini"]["standard"])
    return "gemini-3.8-flash"


def gemini_mini() -> str:
    data = _load()
    if "gemini" in data and "mini" in data["gemini"]:
        return str(data["gemini"]["mini"])
    return "gemini-3.5-flash-lite"
