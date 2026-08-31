"""Отбор и форматирование вакансий.

Чистые функции без сети и без базы — поэтому тестируются мгновенно
и без поднятия бота.
"""

from __future__ import annotations

from typing import Any

MAX_PER_RUN = 5  # больше пяти сообщений подряд — это спам, Telegram зарежет


def extract_new(vacancies: list[dict[str, Any]], already_sent: set[int]) -> list[dict[str, Any]]:
    """Оставить только те вакансии, которые подписчику ещё не уходили."""
    fresh = [v for v in vacancies if int(v["id"]) not in already_sent]
    return fresh[:MAX_PER_RUN]


def format_salary(salary: dict[str, Any] | None) -> str:
    if not salary:
        return "з/п не указана"

    low, high = salary.get("from"), salary.get("to")
    currency = salary.get("currency", "RUR")
    symbol = {"RUR": "₽", "USD": "$", "EUR": "€"}.get(currency, currency)

    if low and high:
        return f"{low:,} – {high:,} {symbol}".replace(",", " ")
    if low:
        return f"от {low:,} {symbol}".replace(",", " ")
    if high:
        return f"до {high:,} {symbol}".replace(",", " ")
    return "з/п не указана"


def format_vacancy(vacancy: dict[str, Any]) -> str:
    """Сообщение для Telegram. Разметка HTML — она надёжнее Markdown,
    который ломается на спецсимволах в названиях компаний."""
    employer = (vacancy.get("employer") or {}).get("name", "—")
    area = (vacancy.get("area") or {}).get("name", "—")
    salary = format_salary(vacancy.get("salary"))
    url = vacancy.get("alternate_url") or f"https://hh.ru/vacancy/{vacancy['id']}"

    return (
        f"<b>{_escape(vacancy.get('name', 'Без названия'))}</b>\n"
        f"{_escape(employer)} · {_escape(area)}\n"
        f"{_escape(salary)}\n\n"
        f'<a href="{url}">Открыть на hh.ru</a>'
    )


def _escape(text: str) -> str:
    """Экранирование под HTML-разметку Telegram."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
