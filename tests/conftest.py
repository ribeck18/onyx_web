from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base, get_session

# Importing the models package registers every model on Base.metadata so that
# create_all builds the full schema and the mapper configures.
import app.models  # noqa: F401
from app.app import app


@pytest_asyncio.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession backed by a throwaway in-memory aiosqlite database.

    StaticPool keeps every connection pointed at the same in-memory database for
    the life of the test; the schema is rebuilt fresh per test for isolation.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with session_factory() as test_session:
        yield test_session

    await engine.dispose()


@pytest_asyncio.fixture
async def client(session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Drive the real app over its HTTP seam against the test session.

    The app's get_session dependency is overridden to hand every request the
    same aiosqlite session the test uses, so route commits and direct reads
    share one in-memory database.
    """

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()
