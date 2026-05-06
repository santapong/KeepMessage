"""Send tools: push_message, get_profile."""

import os
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastmcp import FastMCP

from lib.db import get_pool
from lib.line_client import get_line_client

DEFAULT_USER_ID = os.environ.get("DEFAULT_USER_ID")
PROFILE_TTL = timedelta(hours=24)


def register_send_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    async def push_message(text: str, user_id: Optional[str] = None) -> dict:
        """Send a text message to a LINE user via the Messaging API.

        Args:
            text: message body, max 5000 chars
            user_id: target LINE userId. If omitted, uses DEFAULT_USER_ID env var.
        """
        target = user_id or DEFAULT_USER_ID
        if not target:
            raise ValueError("user_id required (or set DEFAULT_USER_ID)")
        if len(text) > 5000:
            raise ValueError("text exceeds 5000 char limit")

        client = get_line_client()
        resp = await client.post(
            "/v2/bot/message/push",
            json={
                "to": target,
                "messages": [{"type": "text", "text": text}],
            },
        )
        resp.raise_for_status()
        return {"ok": True, "status": resp.status_code}

    @mcp.tool()
    async def get_profile(user_id: str, force_refresh: bool = False) -> dict:
        """Get a LINE user's profile. Cached for 24h in the users table.

        Args:
            user_id: LINE userId
            force_refresh: skip cache and fetch fresh from LINE
        """
        pool = get_pool()
        now = datetime.now(timezone.utc)

        if not force_refresh:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "select user_id, display_name, picture_url, language, fetched_at "
                    "from users where user_id = $1",
                    user_id,
                )
                if row and (now - row["fetched_at"]) < PROFILE_TTL:
                    return dict(row)

        client = get_line_client()
        resp = await client.get(f"/v2/bot/profile/{user_id}")
        if resp.status_code == 404:
            return {"user_id": user_id, "error": "not a friend of this bot"}
        resp.raise_for_status()
        data = resp.json()

        profile = {
            "user_id": user_id,
            "display_name": data.get("displayName"),
            "picture_url": data.get("pictureUrl"),
            "language": data.get("language"),
        }
        async with pool.acquire() as conn:
            await conn.execute(
                """
                insert into users (user_id, display_name, picture_url, language, fetched_at)
                values ($1, $2, $3, $4, now())
                on conflict (user_id) do update set
                  display_name = excluded.display_name,
                  picture_url = excluded.picture_url,
                  language = excluded.language,
                  fetched_at = now()
                """,
                profile["user_id"],
                profile["display_name"],
                profile["picture_url"],
                profile["language"],
            )
        return profile
