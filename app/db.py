from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings
from app.database_url import prepare_database_engine_args


class Base(DeclarativeBase):
    pass


engine: AsyncEngine
SessionLocal: async_sessionmaker[AsyncSession]


def _ensure_sqlite_parent(database_url: str) -> None:
    if database_url.startswith("sqlite") and ":///:memory:" not in database_url:
        db_path = database_url.split("///")[-1]
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)


def configure_engine(database_url: str | None = None) -> AsyncEngine:
    global engine, SessionLocal
    url = database_url or get_settings().database_url
    _ensure_sqlite_parent(url)
    clean_url, connect_args = prepare_database_engine_args(url)
    engine = create_async_engine(clean_url, echo=False, connect_args=connect_args)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    return engine


configure_engine()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    from app.models import tables  # noqa: F401
    from app.schema_migrate import sync_missing_columns

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(sync_missing_columns)


async def reset_db() -> None:
    from app.models import tables  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
