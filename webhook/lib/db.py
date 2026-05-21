"""Supabase client for the webhook side."""

import asyncio
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


def _upsert_sync(rows: list[dict[str, Any]]) -> None:
    _get_client().table("messages").upsert(rows, on_conflict="message_id").execute()


async def insert_messages(rows: list[dict[str, Any]]) -> None:
    """
    Insert message rows. Idempotent on message_id thanks to UNIQUE
    constraint — duplicates from LINE retries are silently skipped.

    supabase-py is sync; offload to a thread so the ASGI event loop
    stays responsive while the network roundtrip happens.
    """
    if not rows:
        return
    await asyncio.to_thread(_upsert_sync, rows)
