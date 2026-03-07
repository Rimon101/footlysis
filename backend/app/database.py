from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

# SQLite needs check_same_thread=False; pool_pre_ping is not supported by aiosqlite
db_url = settings.get_database_url
_is_sqlite = db_url.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}
_engine_kwargs = {"echo": False, "connect_args": _connect_args}
if not _is_sqlite:
    _engine_kwargs["pool_pre_ping"] = True
    _engine_kwargs["pool_size"] = 15
    _engine_kwargs["max_overflow"] = 25

engine = create_async_engine(db_url, **_engine_kwargs)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("[OK] Database tables initialised")
    except Exception as exc:
        print(f"[WARN] Database unavailable on startup ({exc}). "
              "Start PostgreSQL and restart the server to enable persistence.")
