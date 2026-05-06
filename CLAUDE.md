# LINE-MCP

Personal LINE Official Account inbox, readable and replyable from Claude Desktop via MCP.

## Status

Code-complete scaffold. Phase 0 (external setup) is the open work — see [PROJECT-PLAN.md](PROJECT-PLAN.md). Repo is on GitHub at https://github.com/santapong/Line-MCP.

## Two halves of the system

- **Capture** — [webhook/](webhook/) deploys to Vercel. LINE pushes events here, signature is HMAC-verified, message rows are upserted into Supabase.
- **Read + reply** — [mcp/](mcp/) runs locally as a stdio process spawned by Claude Desktop. Reads from Supabase via asyncpg, sends via LINE Messaging API.

The two sides share nothing at runtime except the Supabase database and the LINE channel credentials.

## Where things live

| Concern | File |
|---|---|
| Webhook entrypoint | [webhook/api/webhook.py](webhook/api/webhook.py) |
| HMAC verification | [webhook/lib/line_verify.py](webhook/lib/line_verify.py) |
| Event → row mapping | [webhook/lib/event_parser.py](webhook/lib/event_parser.py) |
| Supabase client (webhook) | [webhook/lib/db.py](webhook/lib/db.py) |
| MCP entrypoint | [mcp/server.py](mcp/server.py) |
| Read tools | [mcp/tools/read.py](mcp/tools/read.py) |
| Send tools | [mcp/tools/send.py](mcp/tools/send.py) |
| asyncpg pool | [mcp/lib/db.py](mcp/lib/db.py) |
| LINE httpx client | [mcp/lib/line_client.py](mcp/lib/line_client.py) |
| Schema | [db/migrations/001_init.sql](db/migrations/001_init.sql) |
| Env template | [.env.example](.env.example) |

## Required environment variables

Webhook (Vercel env vars): `LINE_CHANNEL_SECRET`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`.

MCP (local `.env`): `LINE_CHANNEL_ACCESS_TOKEN`, `SUPABASE_DB_URL`, optional `DEFAULT_USER_ID`.

`SUPABASE_DB_URL` must be the **transaction pooler URI on port 6543** — direct port 5432 will exhaust connections.

## Common commands

```bash
# Apply schema
psql "$SUPABASE_DB_URL" -f db/migrations/001_init.sql

# Run webhook locally (from webhook/)
uvicorn api.webhook:app --reload --port 8000

# Expose locally for LINE webhook verify
cloudflared tunnel --url http://localhost:8000

# Run MCP locally (from mcp/)
uv run python server.py

# Deploy webhook
cd webhook && vercel --prod
```

## Conventions and gotchas

- HMAC verification uses **raw body bytes**. Never re-serialize before verifying — whitespace changes break the signature. See [webhook/lib/line_verify.py](webhook/lib/line_verify.py).
- Inserts are idempotent on `message_id` (LINE retries on 5xx). Don't add app-level dedupe — let `ON CONFLICT` handle it.
- Sends use `pushMessage`, not `replyMessage`. Reply tokens expire in ~30s and Claude can take longer to reason. Push has a 200/month free cap.
- Profiles are cached for 24h in the `users` table. Pass `force_refresh=True` to skip the cache.
- Don't pre-download media. Webhook stores `messageId` only; fetch binary via `/v2/bot/message/{id}/content` on demand.
- The `shared/` directory is empty — Pydantic models were planned but not extracted. Add models there if both sides need them; otherwise keep them local.

## Phase tracker

- [x] Phase 0 — external accounts (LINE, Supabase, Vercel) — **owner: user, blocking everything else**
- [ ] Phase 1 — webhook live, messages landing in Supabase
- [ ] Phase 2 — MCP wired into Claude Desktop, read tools answering correctly
- [ ] Phase 3 — push + profile send tools verified round-trip
- [ ] Phase 4 — pick from polish list (media, groups, semantic search, token rotation, dashboard)

## Docs

[ARCHITECTURE.md](ARCHITECTURE.md) · [PROJECT-PLAN.md](PROJECT-PLAN.md) · [SETUP.md](SETUP.md) · [docs/DATA-MODEL.md](docs/DATA-MODEL.md) · [docs/MCP-TOOLS.md](docs/MCP-TOOLS.md) · [docs/SECURITY.md](docs/SECURITY.md) · [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
