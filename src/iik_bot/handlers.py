import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, ErrorEvent, Message

from iik_bot.catalog import Catalog
from iik_bot.storage import Storage
from iik_bot.views import (
    View,
    card_view,
    menu_view,
    persistent_keyboard,
    role_view,
    search_view,
)

logger = logging.getLogger(__name__)


class Navigation:
    def __init__(self, catalog: Catalog, store: Storage):
        self.catalog = catalog
        self.store = store

    async def open(self, user_id: int, action: str) -> View:
        state = await self.store.get(user_id)
        state.history = [k for k in state.history if k == "menu" or k in self.catalog.cards]
        if not state.history or state.history[0] != "menu":
            state.history.insert(0, "menu")
        if action == "choose_role":
            return role_view()
        if action in {"role:applicant", "role:student"}:
            state.role = "student" if action == "role:student" else "applicant"
            state.history = ["menu"]
        elif action == "menu":
            state.history = ["menu"]
        elif action == "back":
            if len(state.history) > 1:
                state.history.pop()
        elif action.startswith("open:") and action[5:] in self.catalog.cards:
            key = action[5:]
            if state.history[-1] != key:
                state.history.append(key)
        else:
            return View(
                "Эта кнопка устарела. Откройте нужный раздел заново.",
                menu_view(self.catalog, state.role).keyboard,
            )
        await self.store.save(user_id, state)
        key = state.history[-1]
        return (
            menu_view(self.catalog, state.role) if key == "menu" else card_view(self.catalog, key)
        )


async def send_view(message: Message, view: View) -> None:
    await message.answer(view.text, reply_markup=view.keyboard)


def build_router(catalog: Catalog, store: Storage) -> Router:
    router = Router(name="iik_private_chat")
    router.message.filter(F.chat.type == "private")
    router.callback_query.filter(F.message.chat.type == "private")
    nav = Navigation(catalog, store)

    @router.message(CommandStart())
    async def start(message: Message) -> None:
        await message.answer(
            "Здравствуйте! Это справочник ИИК. Основные кнопки всегда под строкой ввода.",
            reply_markup=persistent_keyboard(),
        )
        state = await store.get(message.from_user.id)
        view = await nav.open(message.from_user.id, "menu") if state.role else role_view()
        await send_view(message, view)

    @router.message(Command("menu"))
    @router.message(F.text == "Главное меню")
    async def menu(message: Message) -> None:
        await send_view(message, await nav.open(message.from_user.id, "menu"))

    @router.message(Command("role"))
    async def role(message: Message) -> None:
        await send_view(message, role_view())

    @router.message(F.text == "Назад")
    async def back(message: Message) -> None:
        await send_view(message, await nav.open(message.from_user.id, "back"))

    @router.message(Command("contacts"))
    @router.message(F.text == "Контакты")
    async def contacts(message: Message) -> None:
        await send_view(message, await nav.open(message.from_user.id, "open:contacts"))

    @router.message(Command("help"))
    async def help_message(message: Message) -> None:
        await message.answer(
            "Выбирайте кнопки или напишите вопрос: например, «документы для общежития».\n\n"
            "/menu — главное меню\n/role — сменить роль\n/contacts — контакты служб\n"
            "/search запрос — поиск по справочнику\n/privacy — какие данные хранятся\n"
            "/forget — удалить мои данные\n\n"
            "Условия приёма и работы служб могут меняться. "
            "Проверяйте их по официальным ссылкам в карточках.",
            reply_markup=persistent_keyboard(),
        )

    @router.message(Command("privacy"))
    async def privacy(message: Message) -> None:
        await message.answer(
            "Бот хранит ваш Telegram ID, выбранную роль и последние переходы по меню, "
            "чтобы работали персональный порядок разделов и кнопка «Назад». "
            "Тексты вопросов, имя, телефон и документы в базе не сохраняются. "
            "Не отправляйте сюда паспортные и медицинские документы.\n\n"
            "/forget удаляет сохранённые данные из базы бота. "
            "История чата в Telegram удаляется средствами Telegram."
        )

    @router.message(Command("forget"))
    async def forget(message: Message) -> None:
        await store.delete(message.from_user.id)
        await message.answer("Ваши данные удалены из базы бота.")
        await send_view(message, role_view())

    @router.message(Command("search"))
    async def search_command(message: Message, command: CommandObject) -> None:
        if not command.args:
            await message.answer("Напишите /search и тему, например: /search отсрочка")
            return
        await send_view(message, search_view(catalog, command.args))

    @router.callback_query()
    async def callback(query: CallbackQuery) -> None:
        await query.answer()
        view = await nav.open(query.from_user.id, query.data or "")
        # Старые сообщения также остаются рабочими после перезапуска процесса.
        if not isinstance(query.message, Message):
            return
        try:
            await query.message.edit_text(view.text, reply_markup=view.keyboard)
        except TelegramBadRequest as exc:
            reason = exc.message.lower()
            if "message is not modified" in reason:
                return
            if "message can't be edited" in reason or "message to edit not found" in reason:
                await send_view(query.message, view)
                return
            raise

    @router.message(F.text)
    async def text_message(message: Message) -> None:
        if message.text.startswith("/"):
            await message.answer("Неизвестная команда. Список команд: /help")
            return
        await send_view(message, search_view(catalog, message.text))

    @router.message()
    async def unsupported(message: Message) -> None:
        await message.answer("Я работаю с текстом и кнопками. Выберите раздел: /menu")

    @router.errors()
    async def errors(event: ErrorEvent) -> bool:
        # Не записываем токены, содержимое сообщений и персональные документы в журнал.
        logger.error("Ошибка обработки обновления: %s", type(event.exception).__name__)
        return True

    return router
