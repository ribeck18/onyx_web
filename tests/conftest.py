from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base

# Importing the models package registers every model on Base.metadata so that
# create_all builds the full schema and the mapper configures.
import app.models  # noqa: F401


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
