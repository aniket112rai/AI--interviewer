from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from common.config import settings
from common.models import Base


database_url = make_url(settings.database_url)
if database_url.drivername in {"postgres", "postgresql"}:
    database_url = database_url.set(drivername="postgresql+asyncpg")

database_query = dict(database_url.query)
sslmode = database_query.pop("sslmode", None)
database_url = database_url.set(query=database_query)
connect_args = {"ssl": sslmode} if sslmode else {}

engine = create_async_engine(
    database_url,
    pool_pre_ping=True,
    connect_args=connect_args,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


get_session = get_db


async def create_tables() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(
            text("ALTER TABLE resumes ADD COLUMN IF NOT EXISTS profile_path VARCHAR(1024)")
        )
        await connection.execute(text("ALTER TABLE resumes ADD COLUMN IF NOT EXISTS error TEXT"))
        await connection.execute(
            text("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS profile_snapshot JSONB")
        )
        await connection.execute(text("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS error TEXT"))
        await connection.execute(text("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS duration_sec_actual INTEGER"))
        await connection.execute(text("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS end_reason VARCHAR(32)"))
        await connection.execute(text("ALTER TABLE evaluations ADD COLUMN IF NOT EXISTS answer_quality VARCHAR(16)"))


async def check_database_connection() -> None:
    async with engine.connect():
        pass


async def dispose_database_engine() -> None:
    await engine.dispose()
