import asyncio

from app.database import Base, engine

# Importing the models package registers Project, VendorDataItem, and Revision
# on Base.metadata so create_all builds the full schema.
import app.models  # noqa: F401


async def create_tables() -> None:
    """Create every table on the configured database for local testing."""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_tables())
    print("Tables created.")
