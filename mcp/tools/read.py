"""Read tools: list_recent_messages, search_messages, get_conversation."""

from typing import Optional
from fastmcp import FastMCP

from lib.db import get_pool


def register_read_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    async def list_recent_messages(
        limit: int = 20,
        since: Optional[str] = None,
        source_id: Optional[str] = None,
    ) -> list[dict]:
        """Most recent LINE messages, optionally filtered by time or conversation.

        Args:
            limit: max rows (default 20, hard cap 200)
            since: ISO timestamp; only messages after this
            source_id: limit to one conversation (userId or groupId)
        """
        limit = max(1, min(limit, 200))
        pool = get_pool()
        async with pool.acquire() as conn:
            sql = """
                select id, message_id, source_type, source_id, sender_user_id,
                       message_type, text_content, line_timestamp
                  from messages
                 where ($1::timestamptz is null or line_timestamp > $1)
                   and ($2::text is null or source_id = $2)
                 order by line_timestamp desc
                 limit $3
            """
            rows = await conn.fetch(sql, since, source_id, limit)
            return [dict(r) for r in rows]

    @mcp.tool()
    async def search_messages(
        query: str,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict]:
        """Full-text search across LINE messages.

        Args:
            query: search terms (Postgres tsquery, simplified)
            since: ISO timestamp lower bound
            until: ISO timestamp upper bound
            limit: max rows (default 20)
        """
        limit = max(1, min(limit, 200))
        pool = get_pool()
        async with pool.acquire() as conn:
            sql = """
                select id, source_id, sender_user_id, text_content, line_timestamp
                  from messages
                 where to_tsvector('simple', coalesce(text_content, ''))
                       @@ plainto_tsquery('simple', $1)
                   and ($2::timestamptz is null or line_timestamp >= $2)
                   and ($3::timestamptz is null or line_timestamp <= $3)
                 order by line_timestamp desc
                 limit $4
            """
            rows = await conn.fetch(sql, query, since, until, limit)
            return [dict(r) for r in rows]

    @mcp.tool()
    async def get_conversation(
        source_id: str,
        limit: int = 50,
        before: Optional[str] = None,
    ) -> list[dict]:
        """Threaded view of one conversation.

        Args:
            source_id: userId / groupId / roomId
            limit: max rows (default 50)
            before: ISO timestamp; page backwards from this
        """
        limit = max(1, min(limit, 200))
        pool = get_pool()
        async with pool.acquire() as conn:
            sql = """
                select id, sender_user_id, message_type, text_content, line_timestamp
                  from messages
                 where source_id = $1
                   and ($2::timestamptz is null or line_timestamp < $2)
                 order by line_timestamp desc
                 limit $3
            """
            rows = await conn.fetch(sql, source_id, before, limit)
            return list(reversed([dict(r) for r in rows]))
