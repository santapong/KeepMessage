"""
Map LINE webhook events into DB-ready dicts.

Only `message` events are persisted in v1. Other event types
(follow, unfollow, join, leave, postback) are ignored but can
be added here as needed.
"""

from datetime import datetime, timezone
from typing import Any


def parse_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter to message events and shape them for the messages table."""
    rows: list[dict[str, Any]] = []
    for event in events:
        if event.get("type") != "message":
            continue

        message = event.get("message", {})
        source = event.get("source", {})

        rows.append({
            "message_id": message.get("id"),
            "webhook_event_id": event.get("webhookEventId"),
            "source_type": source.get("type"),
            "source_id": (
                source.get("userId")
                or source.get("groupId")
                or source.get("roomId")
            ),
            "sender_user_id": source.get("userId"),
            "message_type": message.get("type"),
            "text_content": message.get("text") if message.get("type") == "text" else None,
            "raw": event,
            "line_timestamp": datetime.fromtimestamp(
                event.get("timestamp", 0) / 1000.0,
                tz=timezone.utc,
            ).isoformat(),
        })
    return rows
