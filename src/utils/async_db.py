# src/utils/async_db.py
"""
SQLAlchemy 2.0 ASYNC engine (asyncpg) — for the new FastAPI layer + RAG API.
Your existing sync code keeps using src/utils/database.py; this is ONLY for
async endpoints.

Supabase pooler note: asyncpg + the transaction pooler (port 6543) breaks on
prepared statements. We disable the statement cache so it's safe on either
the session pooler (5432, recommended) or 6543.
"""
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession


def _async_url() -> str:
    url = os.getenv("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL not set")
    # ensure the async driver
    if "+asyncpg" not in url:
        url = url.replace("postgresql+psycopg2", "postgresql").replace(
            "postgresql://", "postgresql+asyncpg://")
    return url


engine = create_async_engine(
    _async_url(),
    pool_pre_ping=True,
    connect_args={"statement_cache_size": 0},   # pooler-safe (pgbouncer/transaction mode)
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:           # FastAPI dependency
    async with AsyncSessionLocal() as session:
        yield session