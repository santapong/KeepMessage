"""asyncpg connection pool to Supabase."""

import asyncpg

_pool: asyncpg.Pool | None = None


async def init_db_pool(dsn: str) -> None:
    global _pool
    _pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4)


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("db pool not initialized — call init_db_pool first")
    return _pool
