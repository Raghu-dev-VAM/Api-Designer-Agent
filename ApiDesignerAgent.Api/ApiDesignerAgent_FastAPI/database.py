"""
Database setup — supports SQLite (local/test) and PostgreSQL (production).
  sqlite:///./auth.db           -> sqlite+aiosqlite  (local dev, zero config)
  postgresql://user:pass@host/db -> postgresql+asyncpg (production)
Set DATABASE_URL in .env accordingly.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, DateTime
from datetime import datetime, timezone

from config import settings


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(150), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="user")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


def _make_async_url(url: str) -> str:
    """Convert a standard DB URL to the correct async driver URL."""
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    if url.startswith("sqlite://"):
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://"):]
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


_async_url = _make_async_url(settings.database_url)
_is_sqlite = "sqlite" in _async_url
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

# SQLite doesn't support pool_size/max_overflow
_engine_kwargs = dict(echo=False, pool_pre_ping=True, connect_args=_connect_args)
if not _is_sqlite:
    _engine_kwargs.update(pool_size=5, max_overflow=10)

engine = create_async_engine(_async_url, **_engine_kwargs)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    """Create all tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    """Dependency that yields a database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
