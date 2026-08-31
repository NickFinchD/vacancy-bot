"""Минимальный клиент к API hh.ru — только поиск свежих вакансий."""

from __future__ import annotations

import os
from typing import Any

import httpx

API_URL = "https://api.hh.ru"
USER_AGENT = os.getenv("HH_USER_AGENT", "vacancy-bot/1.0")


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

    async with httpx.AsyncClient(
        base_url=API_URL, headers={"User-Agent": USER_AGENT}, timeout=15.0
    ) as client:
        response = await client.get("/vacancies", params=params)
        response.raise_for_status()
        return response.json().get("items", [])
