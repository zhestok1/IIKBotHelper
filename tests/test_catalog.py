from datetime import date

import pytest
from pydantic import ValidationError

from iik_bot.catalog import Card, Catalog
from iik_bot.views import card_view, menu_view, search_view


def test_all_cards_render_within_telegram_limits(catalog):
    for key in catalog.cards:
        view = card_view(catalog, key)
        assert 0 < len(view.text) <= 4000, key
        assert len(view.keyboard.inline_keyboard) <= 100, key
        for row in view.keyboard.inline_keyboard:
            for button in row:
                if button.callback_data:
                    assert len(button.callback_data.encode()) <= 64
                    if button.callback_data.startswith("open:"):
                        assert button.callback_data[5:] in catalog.cards


def test_both_roles_see_all_sections_in_different_order(catalog):
    applicant = menu_view(catalog, "applicant").keyboard.inline_keyboard
    student = menu_view(catalog, "student").keyboard.inline_keyboard
    assert applicant[0][0].callback_data == "open:admission"
    assert student[0][0].callback_data == "open:dorm"
    assert {row[0].callback_data for row in applicant[:8]} == {
        row[0].callback_data for row in student[:8]
    }


@pytest.mark.parametrize(
    "query,target",
    [
        ("отсрочка", "deferment"),
        ("флюорография", "fluorography"),
        ("расписание", "schedule"),
        ("стипендия ПГАС", "enhanced"),
        ("RoboTIC", "robotic"),
    ],
)
def test_search_finds_expected_topics(catalog, query, target):
    assert target in catalog.search(query)


def test_unknown_search_has_navigation(catalog):
    view = search_view(catalog, "zzzxxyy")
    assert "Не нашёл" in view.text
    assert any(b.callback_data == "menu" for row in view.keyboard.inline_keyboard for b in row)


def test_shared_deferment_and_health_cards(catalog):
    for section in ("documents", "military"):
        assert "deferment" in {c.target for c in catalog.cards[section].children}
    for section in ("dorm_docs", "documents", "health"):
        assert "health_clearance" in {c.target for c in catalog.cards[section].children}


def test_expired_campaign_hides_old_conditions_but_keeps_contact(catalog):
    catalog.cards["admission_rules"] = Card(
        title="Приём",
        text="Старый дедлайн 10 июля",
        steps=["Старый шаг"],
        documents=["Старый документ"],
        campaign_year=2025,
        contact_ids=["admissions"],
        source_ids=["iik"],
    )
    view = card_view(catalog, "admission_rules", date(2026, 10, 17))
    assert "предыдущему периоду" in view.text
    assert "Старый" not in view.text
    assert "priem@ssau.ru" in view.text
    assert any(b.url for row in view.keyboard.inline_keyboard for b in row)


def test_html_is_escaped(catalog):
    catalog.cards["about"].text = "<script> & текст"
    assert "&lt;script&gt; &amp;" in card_view(catalog, "about").text


def test_broken_reference_rejected(catalog):
    raw = catalog.model_dump()
    raw["cards"]["dorm"]["children"][0]["target"] = "missing"
    with pytest.raises(ValidationError, match="неизвестный переход"):
        Catalog.model_validate(raw)


def test_no_editorial_instructions_in_public_answers(catalog):
    for key in catalog.cards:
        text = card_view(catalog, key).text.lower()
        assert "что дополнить" not in text
        assert "предназначен для редактора" not in text
        assert "до публикации карточки" not in text
