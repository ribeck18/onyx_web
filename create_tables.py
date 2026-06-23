import asyncio

from app.database import Base, engine

# Importing the models package registers every mapped class on Base.metadata so
# create_all builds the full schema.
import app.models  # noqa: F401


async def create_tables() -> None:
    """Create every table on the configured database for local testing."""
    async with engine.begin() as connection:
        # TODO(alembic): adopt Alembic for migrations once a schema change must
        # ALTER a table that already holds production data. create_all() only
        # creates missing tables, so it covers purely-additive changes (e.g. the
        # auth tables) but cannot evolve existing ones without data loss.
        await connection.run_sync(Base.metadata.create_all)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_tables())
    print("Tables created.")
