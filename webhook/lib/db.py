"""Supabase client for the webhook side."""

import os
from typing import Any

from supabase import create_client, Client

_client: Client | None = None


def _get_client() -> Client:
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_KEY"]
        _client = create_client(url, key)
    return _client


async def insert_messages(rows: list[dict[str, Any]]) -> None:
    """
    Insert message rows. Idempotent on message_id thanks to UNIQUE
    constraint — duplicates from LINE retries are silently skipped.
    """
    if not rows:
        return
    client = _get_client()
    # upsert with ignore_duplicates=True equivalent: rely on PG ON CONFLICT
    # via a tiny RPC, OR insert and swallow unique-violation errors.
    # Simplest path for v1: upsert with on_conflict='message_id'.
    client.table("messages").upsert(rows, on_conflict="message_id").execute()
