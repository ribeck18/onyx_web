from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from pathlib import Path

from app.auth import service as auth_service
from app.database import Base, get_session
from app.file.dependencies import get_storage_root
from app.models.user import User

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


async def seed_user(
    session: AsyncSession,
    email: str = "tester@onyx.test",
    is_admin: bool = False,
) -> User:
    """Persist an active, already-bound User for tests that need a real account."""
    user = User(
        entra_oid=f"oid-{email}",
        email=email,
        display_name="Test User",
        is_admin=is_admin,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    return user


def _build_client(session: AsyncSession, tmp_path: Path) -> AsyncClient:
    """Build an AsyncClient over the app, sharing the test session and tmp uploads."""

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_storage_root] = lambda: tmp_path
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest_asyncio.fixture
async def client(
    session: AsyncSession,
    tmp_path: Path,
) -> AsyncGenerator[AsyncClient, None]:
    """Drive the real app, authenticated by default, against the test session.

    A User and a minted Session are seeded into the shared in-memory database and
    the session cookie is sent on every request, so the global auth gate (which
    runs at the ASGI layer) admits the whole existing suite without per-test
    edits. get_storage_root is redirected to pytest's per-test tmp_path.
    """
    user = await seed_user(session)
    raw_token, _ = await auth_service.mint_session(session, user)

    test_client = _build_client(session, tmp_path)
    test_client.cookies.set(auth_service.SESSION_COOKIE_NAME, raw_token)
    async with test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_client(
    session: AsyncSession,
    tmp_path: Path,
) -> AsyncGenerator[AsyncClient, None]:
    """Drive the app authenticated as an admin, for the account-management routes."""
    admin = await seed_user(session, email="admin@onyx.test", is_admin=True)
    raw_token, _ = await auth_service.mint_session(session, admin)

    test_client = _build_client(session, tmp_path)
    test_client.cookies.set(auth_service.SESSION_COOKIE_NAME, raw_token)
    async with test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def anonymous_client(
    session: AsyncSession,
    tmp_path: Path,
) -> AsyncGenerator[AsyncClient, None]:
    """Drive the app with no session cookie, to assert the unauthenticated gate."""
    test_client = _build_client(session, tmp_path)
    async with test_client:
        yield test_client
    app.dependency_overrides.clear()
