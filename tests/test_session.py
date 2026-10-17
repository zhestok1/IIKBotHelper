from iik_bot.session import EnvironmentSession


async def test_http_session_uses_environment_and_can_reopen():
    session = EnvironmentSession()
    try:
        first = await session.create_session()
        assert first.trust_env is True
        assert await session.create_session() is first
        await session.close()
        assert first.closed
        second = await session.create_session()
        assert second is not first
        assert not second.closed
    finally:
        await session.close()
