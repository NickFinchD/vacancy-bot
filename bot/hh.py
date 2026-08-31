"""Минимальный клиент к API hh.ru — только поиск свежих вакансий."""

from __future__ import annotations

import os
from typing import Any

import httpx

API_URL = "https://api.hh.ru"
USER_AGENT = os.getenv("HH_USER_AGENT", "vacancy-bot/1.0")

# С 2026 года API hh.ru отвечает 403 на анонимные запросы — даже на публичный
# поиск вакансий. Токен приложения получается один раз на https://dev.hh.ru/admin
ACCESS_TOKEN = os.getenv("HH_ACCESS_TOKEN", "")


class MissingTokenError(RuntimeError):
    """API отклонило запрос из-за отсутствующего или недействительного токена."""


def build_headers() -> dict[str, str]:
    headers = {"User-Agent": USER_AGENT}
    if ACCESS_TOKEN:
        headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"
    return headers


async def search_recent(query: str, period_days: int = 1, limit: int = 20) -> list[dict[str, Any]]:
    """Вакансии по запросу за последние period_days, только удалёнка.

    Сортировка по дате публикации: смысл бота в том, чтобы подписчик увидел
    вакансию в первые часы, пока на неё не пришли сотни откликов.
    """
    params = {
        "text": query,
        "period": period_days,
        "schedule": "remote",
        "order_by": "publication_time",
        "per_page": limit,
    }

    async with httpx.AsyncClient(base_url=API_URL, headers=build_headers(), timeout=15.0) as client:
        response = await client.get("/vacancies", params=params)

        if response.status_code == 403:
            # Без этой ветки в логах будет голое "403 Forbidden",
            # и причина остаётся неочевидной
            raise MissingTokenError(
                "hh.ru ответил 403. Нужен токен приложения: получи его на "
                "https://dev.hh.ru/admin и задай переменную HH_ACCESS_TOKEN."
            )

        response.raise_for_status()
        return response.json().get("items", [])
