import json
from dataclasses import dataclass
from pathlib import Path

import aiosqlite

from iik_bot.catalog import Role


@dataclass
class UserState:
    role: Role | None
    history: list[str]


class Storage:
    """Хранит только Telegram ID, роль и путь по справочнику, без текстов сообщений."""

    def __init__(self, path: Path):
        self.path = path
        self.connection: aiosqlite.Connection | None = None

    @property
    def db(self) -> aiosqlite.Connection:
        if self.connection is None:
            raise RuntimeError("Хранилище не открыто")
        return self.connection

    async def open(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = await aiosqlite.connect(self.path)
        await self.db.execute("PRAGMA journal_mode=WAL")
        await self.db.execute("PRAGMA busy_timeout=5000")
        await self.db.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "user_id INTEGER PRIMARY KEY, role TEXT, history TEXT NOT NULL)"
        )
        await self.db.commit()

    async def close(self) -> None:
        if self.connection:
            await self.connection.close()
            self.connection = None

    async def get(self, user_id: int) -> UserState:
        async with self.db.execute(
            "SELECT role, history FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return UserState(None, ["menu"])
        role = row[0] if row[0] in ("applicant", "student") else None
        return UserState(role, json.loads(row[1]))

    async def save(self, user_id: int, state: UserState) -> None:
        if len(state.history) > 50:
            state.history = state.history[:1] + state.history[-49:]
        await self.db.execute(
            "INSERT INTO users (user_id, role, history) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET role=excluded.role, history=excluded.history",
            (user_id, state.role, json.dumps(state.history)),
        )
        await self.db.commit()

    async def delete(self, user_id: int) -> None:
        await self.db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        await self.db.commit()
