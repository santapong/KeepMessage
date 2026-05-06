"""
LINE webhook receiver. Deployed to Vercel.

Responsibilities:
1. Verify HMAC-SHA256 signature against raw body.
2. Parse webhook events.
3. Insert messages into Supabase (idempotent on message_id).
4. Return 200 OK quickly (LINE retries on 5xx).

Heavy work belongs elsewhere — this handler must respond fast.
"""

import os
import json
from fastapi import FastAPI, Request, HTTPException

from lib.line_verify import verify_signature
from lib.event_parser import parse_events
from lib.db import insert_messages

CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]

app = FastAPI()


@app.post("/api/webhook")
async def webhook(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("x-line-signature", "")

    if not verify_signature(raw_body, signature, CHANNEL_SECRET):
        # Don't log body — could be attacker probes.
        raise HTTPException(status_code=401, detail="invalid signature")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid json")

    rows = parse_events(payload.get("events", []))
    if rows:
        await insert_messages(rows)

    return {"ok": True}


@app.get("/api/webhook")
async def health():
    """For UptimeRobot pings and quick browser sanity check."""
    return {"status": "ok"}
