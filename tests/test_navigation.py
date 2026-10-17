from iik_bot.handlers import Navigation
from iik_bot.storage import Storage


async def test_history_returns_from_cross_link_to_original_section(catalog, store):
    nav = Navigation(catalog, store)
    await nav.open(1, "role:student")
    await nav.open(1, "open:documents")
    await nav.open(1, "open:deferment")
    await nav.open(1, "open:military_registry")
    assert "Справка для отсрочки" in (await nav.open(1, "back")).text
    assert "Справки и документы" in (await nav.open(1, "back")).text
    assert "Главное меню" in (await nav.open(1, "back")).text
    assert (await store.get(1)).history == ["menu"]
    await nav.open(1, "back")
    assert (await store.get(1)).history == ["menu"]


async def test_repeated_clicks_and_unknown_callback(catalog, store):
    nav = Navigation(catalog, store)
    await nav.open(1, "open:study")
    await nav.open(1, "open:study")
    assert (await store.get(1)).history == ["menu", "study"]
    assert "устарела" in (await nav.open(1, "open:unknown")).text
    assert (await store.get(1)).history == ["menu", "study"]


async def test_persistence_and_deletion(catalog, tmp_path):
    path = tmp_path / "persistent.sqlite3"
    first = Storage(path)
    await first.open()
    try:
        nav = Navigation(catalog, first)
        await nav.open(42, "role:student")
        await nav.open(42, "open:dorm")
    finally:
        await first.close()
    second = Storage(path)
    await second.open()
    try:
        state = await second.get(42)
        assert state.role == "student"
        assert state.history == ["menu", "dorm"]
        assert (await second.get(43)).role is None
        await second.delete(42)
        assert (await second.get(42)).role is None
    finally:
        await second.close()


async def test_history_is_bounded_and_menu_recovers(catalog, store):
    nav = Navigation(catalog, store)
    for i in range(80):
        await nav.open(1, "open:study" if i % 2 else "open:dorm")
    assert len((await store.get(1)).history) <= 50
    assert (await store.get(1)).history[0] == "menu"
    await nav.open(1, "menu")
    assert (await store.get(1)).history == ["menu"]
