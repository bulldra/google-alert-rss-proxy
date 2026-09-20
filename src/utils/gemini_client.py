import json
import logging
import os
from typing import Any

from google import genai

_logger = logging.getLogger(__name__)

_client_cache: dict[tuple[str | None, str], genai.Client] = {}


def get_gemini_client(
    context: dict[str, Any] | None = None,
    location: str | None = None,
) -> genai.Client:
    """Google Cloud Functions / Vertex AI 向けの Gemini クライアントを生成する。

    API Key は使用せず、Cloud Functions のサービスアカウント認証 (ADC) を利用する。
    Gemini 3.5 Flash Lite などのモデルは global ロケーションで提供されるため、
    デフォルトで global を使用する。
    コネクションプールとリソース再利用のため、
    (project, location) ごとにクライアントをキャッシュする。
    """
    context = context or {}

    secrets: dict[str, Any] = {}
    secrets_raw = os.getenv("SECRETS")
    if secrets_raw:
        try:
            secrets = json.loads(secrets_raw)
        except Exception:
            pass

    project = (
        context.get("GCP_PROJECT")
        or secrets.get("GCP_PROJECT")
        or os.getenv("GOOGLE_CLOUD_PROJECT")
        or os.getenv("GCP_PROJECT")
    )

    client_location = (
        location
        or os.getenv("GEMINI_LOCATION")
        or "global"
    )

    cache_key = (project, client_location)
    if cache_key not in _client_cache:
        _logger.debug(
            "Creating new Gemini Client with Vertex AI: project=%s, location=%s",
            project,
            client_location,
        )
        _client_cache[cache_key] = genai.Client(
            vertexai=True,
            project=project,
            location=client_location,
        )
    return _client_cache[cache_key]


def clear_client_cache() -> None:
    """テスト用にキャッシュをクリアする関数。"""
    _client_cache.clear()
