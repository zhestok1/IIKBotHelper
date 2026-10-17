from dataclasses import dataclass
from datetime import date
from html import escape

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from iik_bot.catalog import Catalog, Role


@dataclass(frozen=True)
class View:
    text: str
    keyboard: InlineKeyboardMarkup


def button(label: str, action: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=label, callback_data=action)


def navigation() -> list[list[InlineKeyboardButton]]:
    return [
        [button("← Назад", "back"), button("Главное меню", "menu")],
        [button("Контакты", "open:contacts")],
    ]


def persistent_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Главное меню"), KeyboardButton(text="Назад")],
            [KeyboardButton(text="Контакты")],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Выберите раздел или напишите вопрос",
    )


def role_view() -> View:
    return View(
        "<b>Помощник ИИК</b>\n\n"
        "Помогу с поступлением, заселением, документами и студенческой жизнью "
        "в Самарском университете.\n\nВы поступаете или уже зачислены? "
        "Выбор меняет порядок подсказок — все разделы остаются доступны.",
        InlineKeyboardMarkup(
            inline_keyboard=[
                [button("Поступаю", "role:applicant"), button("Уже зачислен", "role:student")],
                [button("Все разделы", "menu")],
            ]
        ),
    )


def menu_view(catalog: Catalog, role: Role | None) -> View:
    hint = (
        "Начните с заселения, документов и расписания."
        if role == "student"
        else "Начните с поступления и общежития."
    )
    rows = [[button(catalog.cards[k].title, f"open:{k}")] for k in catalog.menu(role)]
    rows += [[button("Контакты", "open:contacts"), button("Сменить роль", "choose_role")]]
    return View(
        f"<b>Главное меню</b>\n\n{hint}\n"
        "Выберите раздел или напишите вопрос для поиска по справочнику.",
        InlineKeyboardMarkup(inline_keyboard=rows),
    )


def card_view(catalog: Catalog, key: str, today: date | None = None) -> View:
    card = catalog.cards[key]
    expired = card.expired(today or date.today())
    parts = [f"<b>{escape(card.title)}</b>"]
    if expired:
        parts.append(
            "Сведения относятся к предыдущему периоду. "
            "Уточните действующие условия по официальному источнику или у службы ниже."
        )
    else:
        parts.append(escape(card.text))
        if card.steps:
            parts.append(
                "<b>Что сделать</b>\n"
                + "\n".join(f"{i}. {escape(s)}" for i, s in enumerate(card.steps, 1))
            )
        if card.documents:
            parts.append("<b>Документы</b>\n" + "\n".join(f"• {escape(s)}" for s in card.documents))
    for contact_id in card.contact_ids:
        contact = catalog.contacts[contact_id]
        parts.append(f"<b>{escape(contact.title)}</b>\n{escape(contact.details)}")
    rows = [[button(link.label, f"open:{link.target}")] for link in card.children]
    for source_id in card.source_ids:
        source = catalog.sources[source_id]
        rows.append([InlineKeyboardButton(text=f"↗ {source.label}", url=source.url)])
    rows += navigation()
    return View("\n\n".join(parts), InlineKeyboardMarkup(inline_keyboard=rows))


def search_view(catalog: Catalog, query: str) -> View:
    results = catalog.search(query)
    text = (
        "Выберите подходящую тему:"
        if results
        else "Не нашёл подходящую карточку. Попробуйте «общежитие», "
        "«отсрочка», «расписание» или откройте раздел и контакты."
    )
    return View(
        f"<b>Поиск по справочнику</b>\n\n{text}",
        InlineKeyboardMarkup(
            inline_keyboard=[
                *[[button(catalog.cards[k].title, f"open:{k}")] for k in results],
                *navigation(),
            ]
        ),
    )
