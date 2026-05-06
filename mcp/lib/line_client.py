"""Thin httpx wrapper for the LINE Messaging API."""

import httpx

LINE_API_BASE = "https://api.line.me"

_client: httpx.AsyncClient | None = None


def init_line_client(channel_access_token: str) -> None:
    global _client
    _client = httpx.AsyncClient(
        base_url=LINE_API_BASE,
        headers={"Authorization": f"Bearer {channel_access_token}"},
        timeout=10.0,
    )


def get_line_client() -> httpx.AsyncClient:
    if _client is None:
        raise RuntimeError("line client not initialized — call init_line_client first")
    return _client
