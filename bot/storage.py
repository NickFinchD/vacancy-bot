"""Хранилище подписок и истории отправок.

Здесь намеренно голый sqlite3 без ORM: таблиц две, запросов пять,
подключать SQLAlchemy ради этого — лишняя зависимость.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

SCHEMA = """
CREATE TABLE IF NOT EXISTS subscriptions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id    INTEGER NOT NULL,
    query      TEXT    NOT NULL,
    created_at TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (chat_id, query)
);

-- Защита от повторной отправки: одна вакансия уходит подписчику один раз.
CREATE TABLE IF NOT EXISTS sent (
    chat_id    INTEGER NOT NULL,
    vacancy_id INTEGER NOT NULL,
    sent_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (chat_id, vacancy_id)
);

CREATE INDEX IF NOT EXISTS ix_subscriptions_chat ON subscriptions (chat_id);
"""


@dataclass(frozen=True)
class Subscription:
    id: int
    chat_id: int
    query: str


class Storage:
    def __init__(self, path: str = "bot.db") -> None:
        self._path = path
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def add_subscription(self, chat_id: int, query: str) -> bool:
        """Добавить подписку. False — если такая уже есть."""
        with self._connect() as conn:
            try:
                conn.execute(
                    "INSERT INTO subscriptions (chat_id, query) VALUES (?, ?)",
                    (chat_id, query.strip().lower()),
                )
            except sqlite3.IntegrityError:
                return False
            return True

    def remove_subscription(self, chat_id: int, query: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM subscriptions WHERE chat_id = ? AND query = ?",
                (chat_id, query.strip().lower()),
            )
            return cursor.rowcount > 0

    def list_subscriptions(self, chat_id: int) -> list[Subscription]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, chat_id, query FROM subscriptions WHERE chat_id = ? ORDER BY id",
                (chat_id,),
            ).fetchall()
        return [Subscription(r["id"], r["chat_id"], r["query"]) for r in rows]

    def all_subscriptions(self) -> list[Subscription]:
        """Все подписки — нужны фоновому опросу."""
        with self._connect() as conn:
            rows = conn.execute("SELECT id, chat_id, query FROM subscriptions").fetchall()
        return [Subscription(r["id"], r["chat_id"], r["query"]) for r in rows]

    def already_sent(self, chat_id: int) -> set[int]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT vacancy_id FROM sent WHERE chat_id = ?", (chat_id,)
            ).fetchall()
        return {r["vacancy_id"] for r in rows}

    def mark_sent(self, chat_id: int, vacancy_ids: list[int]) -> None:
        if not vacancy_ids:
            return
        with self._connect() as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO sent (chat_id, vacancy_id) VALUES (?, ?)",
                [(chat_id, vid) for vid in vacancy_ids],
            )
