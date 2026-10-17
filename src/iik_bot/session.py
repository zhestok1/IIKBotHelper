import ssl

from aiogram.client.session.aiohttp import AiohttpSession
from aiohttp import ClientSession, TCPConnector


class EnvironmentSession(AiohttpSession):
    """Стандартные HTTPS_PROXY/NO_PROXY и системный trust store облачной среды.

    Сериализация Telegram API и обработка его ответов остаются в aiogram.
    Собственная HTTP-сессия позволяет не менять внутренние настройки aiogram.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.http_session: ClientSession | None = None

    async def create_session(self) -> ClientSession:
        if self.http_session is None or self.http_session.closed:
            self.http_session = ClientSession(
                trust_env=True,
                connector=TCPConnector(ssl=ssl.create_default_context()),
            )
        return self.http_session

    async def close(self) -> None:
        if self.http_session is not None:
            await self.http_session.close()
            self.http_session = None
