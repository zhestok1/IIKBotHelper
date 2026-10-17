import argparse
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.storage.memory import SimpleEventIsolation
from aiogram.types import BotCommand, LinkPreviewOptions
from aiogram.utils.token import TokenValidationError, validate_token

from iik_bot.catalog import load_catalog
from iik_bot.config import Settings
from iik_bot.handlers import build_router
from iik_bot.session import EnvironmentSession
from iik_bot.storage import Storage
from iik_bot.views import card_view


def check_content(settings: Settings) -> None:
    catalog = load_catalog(settings.content_path)
    for key in catalog.cards:
        view = card_view(catalog, key)
        if len(view.text) > 4000:
            raise ValueError(f"Слишком длинная карточка: {key}")
        for row in view.keyboard.inline_keyboard:
            for button in row:
                if button.callback_data and len(button.callback_data.encode()) > 64:
                    raise ValueError(f"Слишком длинная callback_data: {key}")
    print(f"Каталог корректен: {len(catalog.sections)} разделов, {len(catalog.cards)} карточек.")


async def run(settings: Settings) -> None:
    if not settings.token:
        raise ValueError("Задайте BOT_TOKEN в .env или настройках среды (токен от @BotFather).")
    try:
        validate_token(settings.token)
    except TokenValidationError:
        raise ValueError(
            "BOT_TOKEN имеет неверный формат. Проверьте токен от @BotFather."
        ) from None
    catalog = load_catalog(settings.content_path)
    store = Storage(settings.database_path)
    bot = Bot(
        settings.token,
        session=EnvironmentSession(),
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            link_preview=LinkPreviewOptions(is_disabled=True),
        ),
    )
    # Изоляция последовательных действий одного пользователя защищает историю переходов.
    dispatcher = Dispatcher(events_isolation=SimpleEventIsolation())
    dispatcher.include_router(build_router(catalog, store))
    try:
        await store.open()
        webhook = await bot.get_webhook_info()
        if webhook.url:
            raise ValueError(
                "У бота настроен webhook. Перед polling удалите его осознанно через "
                "Telegram API или используйте отдельного бота для разработки."
            )
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Начать работу"),
                BotCommand(command="menu", description="Главное меню"),
                BotCommand(command="role", description="Поступаю / уже зачислен"),
                BotCommand(command="contacts", description="Контакты служб"),
                BotCommand(command="search", description="Поиск по справочнику"),
                BotCommand(command="help", description="Помощь"),
                BotCommand(command="privacy", description="Хранение данных"),
                BotCommand(command="forget", description="Удалить мои данные"),
            ]
        )
        logging.getLogger(__name__).info("Бот запущен в режиме long polling")
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        await dispatcher.storage.close()
        await dispatcher.fsm.events_isolation.close()
        await bot.session.close()
        await store.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Telegram-помощник ИИК")
    parser.add_argument("--check", action="store_true", help="Проверить каталог без токена и сети")
    args = parser.parse_args()
    try:
        settings = Settings.load()
        logging.basicConfig(level=settings.log_level, format="%(levelname)s %(name)s: %(message)s")
        if args.check:
            check_content(settings)
        else:
            asyncio.run(run(settings))
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Ошибка: {exc}\n")
    except TelegramAPIError as exc:
        # Сетевые исключения могут содержать URL с токеном; не печатаем их целиком.
        parser.exit(
            1,
            f"Не удалось подключиться к Telegram ({type(exc).__name__}). "
            "Проверьте BOT_TOKEN, доступ к api.telegram.org "
            "и отсутствие другого polling-процесса.\n",
        )


if __name__ == "__main__":
    main()
