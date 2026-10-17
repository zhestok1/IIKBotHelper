from pathlib import Path

import pytest
from aiogram import Dispatcher
from aiogram.methods import GetWebhookInfo, SetMyCommands
from test_handlers import RecordingSession

from iik_bot import __main__ as entry
from iik_bot.config import Settings


def settings(path: Path, token: str = "123456789:" + "A" * 35) -> Settings:
    return Settings(token=token, database_path=path, content_path=None, log_level="INFO")


async def test_missing_token_fails_before_opening_database(tmp_path):
    path = tmp_path / "bot.sqlite3"
    with pytest.raises(ValueError, match="Задайте BOT_TOKEN"):
        await entry.run(settings(path, token=""))
    assert not path.exists()


async def test_startup_registers_commands_and_closes_resources(tmp_path, monkeypatch):
    session = RecordingSession()
    polled = []

    async def polling(self, bot, **kwargs):
        polled.append(kwargs["allowed_updates"])

    monkeypatch.setattr(entry, "EnvironmentSession", lambda: session)
    monkeypatch.setattr(Dispatcher, "start_polling", polling)
    await entry.run(settings(tmp_path / "bot.sqlite3"))
    assert polled == [["callback_query", "message"]]
    assert isinstance(session.calls[0], GetWebhookInfo)
    assert isinstance(session.calls[1], SetMyCommands)
    assert {c.command for c in session.calls[1].commands} >= {"start", "menu", "forget"}
    assert session.closed


async def test_existing_webhook_is_not_deleted(tmp_path, monkeypatch):
    session = RecordingSession()
    session.webhook_url = "https://example.org/webhook"
    monkeypatch.setattr(entry, "EnvironmentSession", lambda: session)
    with pytest.raises(ValueError, match="настроен webhook"):
        await entry.run(settings(tmp_path / "bot.sqlite3"))
    assert len(session.calls) == 1
    assert isinstance(session.calls[0], GetWebhookInfo)
    assert session.closed
