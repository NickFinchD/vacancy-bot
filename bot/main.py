"""Телеграм-бот: присылает новые вакансии по подпискам.

Запуск: BOT_TOKEN=... python -m bot.main
"""

from __future__ import annotations

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from .hh import search_recent
from .matcher import extract_new, format_vacancy
from .storage import Storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "900"))  # 15 минут

storage = Storage(os.getenv("DB_PATH", "bot.db"))
dispatcher = Dispatcher()


@dispatcher.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Присылаю новые удалённые вакансии с hh.ru в первые минуты после публикации.\n\n"
        "<b>Команды</b>\n"
        "/add python — подписаться на запрос\n"
        "/list — мои подписки\n"
        "/del python — отписаться"
    )


@dispatcher.message(Command("add"))
async def cmd_add(message: Message, command: CommandObject) -> None:
    query = (command.args or "").strip()
    if not query:
        await message.answer("Укажи запрос: <code>/add python</code>")
        return

    if storage.add_subscription(message.chat.id, query):
        await message.answer(f"Подписка на «{html.quote(query)}» добавлена.")
    else:
        await message.answer("Такая подписка уже есть.")


@dispatcher.message(Command("del"))
async def cmd_del(message: Message, command: CommandObject) -> None:
    query = (command.args or "").strip()
    if storage.remove_subscription(message.chat.id, query):
        await message.answer(f"Подписка на «{html.quote(query)}» удалена.")
    else:
        await message.answer("Такой подписки не нашёл. Посмотреть свои — /list")


@dispatcher.message(Command("list"))
async def cmd_list(message: Message) -> None:
    subscriptions = storage.list_subscriptions(message.chat.id)
    if not subscriptions:
        await message.answer("Подписок нет. Добавить: <code>/add python</code>")
        return

    lines = "\n".join(f"• {html.quote(s.query)}" for s in subscriptions)
    await message.answer(f"<b>Твои подписки</b>\n{lines}")


async def poll_once(bot: Bot) -> int:
    """Один проход по всем подпискам. Возвращает число отправленных сообщений."""
    sent_count = 0

    for subscription in storage.all_subscriptions():
        try:
            vacancies = await search_recent(subscription.query)
        except Exception as exc:  # один сломанный запрос не должен ронять цикл
            logger.error("Поиск «%s» не удался: %s", subscription.query, exc)
            continue

        fresh = extract_new(vacancies, storage.already_sent(subscription.chat_id))
        for vacancy in fresh:
            try:
                await bot.send_message(subscription.chat_id, format_vacancy(vacancy))
                sent_count += 1
            except Exception as exc:
                logger.error("Не отправил в чат %s: %s", subscription.chat_id, exc)
                continue
            # Пауза между сообщениями — у Telegram есть лимит частоты
            await asyncio.sleep(0.5)

        storage.mark_sent(subscription.chat_id, [int(v["id"]) for v in fresh])

    return sent_count


async def poller(bot: Bot) -> None:
    while True:
        count = await poll_once(bot)
        logger.info("Проход завершён, отправлено сообщений: %s", count)
        await asyncio.sleep(POLL_INTERVAL)


async def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise SystemExit("Не задан BOT_TOKEN. Получи токен у @BotFather.")

    bot = Bot(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    asyncio.create_task(poller(bot))
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
