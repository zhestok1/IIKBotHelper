from datetime import UTC, datetime

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import (
    AnswerCallbackQuery,
    EditMessageText,
    GetWebhookInfo,
    SendMessage,
    SetMyCommands,
)
from aiogram.types import CallbackQuery, Chat, Message, Update, User, WebhookInfo

from iik_bot.handlers import build_router


class RecordingSession(BaseSession):
    """Telegram API double: реальные Update проходят через Dispatcher и фильтры."""

    def __init__(self):
        super().__init__()
        self.calls = []
        self.edit_error = None
        self.closed = False
        self.webhook_url = ""

    async def close(self):
        self.closed = True

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        if isinstance(method, GetWebhookInfo):
            return WebhookInfo(
                url=self.webhook_url, has_custom_certificate=False, pending_update_count=0
            )
        if isinstance(method, SetMyCommands):
            return True
        if isinstance(method, AnswerCallbackQuery):
            return True
        if isinstance(method, EditMessageText) and self.edit_error:
            raise TelegramBadRequest(method=method, message=self.edit_error)
        if isinstance(method, (SendMessage, EditMessageText)):
            return Message(
                message_id=len(self.calls),
                date=datetime.now(UTC),
                chat=Chat(id=int(method.chat_id), type="private"),
                text=method.text,
            )
        raise AssertionError(f"Неожиданный Telegram-метод: {type(method).__name__}")

    async def stream_content(
        self, url, headers=None, timeout=30, chunk_size=65536, raise_for_status=True
    ):
        yield b""


@pytest.fixture
async def app(catalog, store):
    session = RecordingSession()
    # Только синтаксически допустимый тестовый токен, никогда не отправляется в сеть.
    bot = Bot(
        "123456789:" + "A" * 35, session=session, default=DefaultBotProperties(parse_mode="HTML")
    )
    dp = Dispatcher()
    dp.include_router(build_router(catalog, store))
    try:
        yield dp, bot, session
    finally:
        await dp.storage.close()
        await bot.session.close()


def message(text, user_id=42, chat_type="private"):
    return Message(
        message_id=1,
        date=datetime.now(UTC),
        chat=Chat(id=user_id, type=chat_type),
        from_user=User(id=user_id, is_bot=False, first_name="Тест"),
        text=text,
    )


async def send(app, text):
    dp, bot, session = app
    await dp.feed_update(bot, Update(update_id=len(session.calls), message=message(text)))


async def click(app, action):
    dp, bot, session = app
    query = CallbackQuery(
        id="test-callback",
        from_user=User(id=42, is_bot=False, first_name="Тест"),
        chat_instance="private",
        message=message("previous"),
        data=action,
    )
    await dp.feed_update(bot, Update(update_id=len(session.calls), callback_query=query))


async def test_start_role_navigation_search_and_forget(app, store, caplog):
    _, _, session = app
    await send(app, "/start")
    assert len(session.calls) == 2
    assert session.calls[0].reply_markup.is_persistent
    assert "Поступаю" in session.calls[-1].reply_markup.model_dump_json()
    await click(app, "role:student")
    assert isinstance(session.calls[-2], AnswerCallbackQuery)
    assert session.calls[-1].reply_markup.inline_keyboard[0][0].callback_data == "open:dorm"
    assert (await store.get(42)).role == "student"
    await click(app, "open:dorm")
    assert "Общежитие" in session.calls[-1].text
    await click(app, "open:dorm_docs")
    await click(app, "back")
    assert "Общежитие" in session.calls[-1].text
    await send(app, "Контакты")
    assert "Контакты служб" in session.calls[-1].text
    await send(app, "/search отсрочка")
    results = session.calls[-1].reply_markup.inline_keyboard
    assert any(b.callback_data == "open:deferment" for row in results for b in row)
    await send(app, "/forget")
    assert (await store.get(42)).role is None
    assert not [r for r in caplog.records if r.levelname == "ERROR"]


async def test_every_card_is_delivered_by_callback(app, catalog, caplog):
    session = app[2]
    for key, card in catalog.cards.items():
        await click(app, f"open:{key}")
        assert isinstance(session.calls[-1], EditMessageText)
        assert card.title in session.calls[-1].text
    assert not [r for r in caplog.records if r.levelname == "ERROR"]


async def test_unchanged_message_is_accepted(app, caplog):
    app[2].edit_error = "Bad Request: message is not modified"
    await click(app, "menu")
    assert not [r for r in caplog.records if r.levelname == "ERROR"]


async def test_uneditable_message_falls_back_to_new_message(app):
    app[2].edit_error = "Bad Request: message can't be edited"
    await click(app, "open:study")
    assert isinstance(app[2].calls[-1], SendMessage)
    assert "Учёба и сервисы" in app[2].calls[-1].text


async def test_commands_and_plain_text(app):
    session = app[2]
    await send(app, "/search")
    assert "Напишите /search" in session.calls[-1].text
    await send(app, "/unknown")
    assert "Неизвестная команда" in session.calls[-1].text
    await send(app, "расписание")
    assert "Поиск по справочнику" in session.calls[-1].text
    await send(app, "/privacy")
    assert "не сохраняются" in session.calls[-1].text


async def test_group_messages_ignored(app):
    dp, bot, session = app
    await dp.feed_update(bot, Update(update_id=100, message=message("/start", chat_type="group")))
    assert session.calls == []
