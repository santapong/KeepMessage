# Project Plan

## Goal

Build a personal LINE inbox that Claude Desktop can read and reply to via MCP. Optimized for solo use, $0/month operating cost, and minimal moving parts.

## Success criteria

By end of Phase 3, you can:
1. DM your LINE bot from your phone and see the message in Supabase within 2 seconds.
2. Open Claude Desktop and ask *"What did I get on LINE today?"* and receive a correct summary.
3. Tell Claude *"Reply to that with X"* and your friend receives the message.

---

## Cost analysis

| Service | Tier | Personal cost |
|---|---|---|
| LINE Messaging API | Free | $0 (200 push/month, unlimited replies, unlimited webhooks) |
| Vercel | Hobby | $0 (100 GB bandwidth, 100 GB-hr functions/month) |
| Supabase | Free | $0 (500 MB DB, 5 GB egress) |
| Cloudflare Tunnel | Free | $0 (dev only) |
| Claude Desktop | Your existing plan | $0 incremental |

**Total: $0/month** for personal-bot use. Only scenarios that incur cost: broadcasting to many users (LINE push cap), heavy DB usage (Supabase scale), or paid embedding APIs.

---

## Phased plan

### 🟢 Phase 0 — Pre-flight (1–2 hours)

| Task | Output |
|---|---|
| Create LINE Provider + Messaging API channel | Channel ID, Channel Secret, Bot Basic ID |
| Issue Channel Access Token v2.1 | Token saved to password manager |
| Disable auto-reply + greeting in LINE Official Account Manager | Bot stays silent until your code responds |
| Create Supabase project | `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_DB_URL` |
| Run `db/migrations/001_init.sql` | Three tables exist: `messages`, `users`, `bot_state` |
| Create Vercel project, link to GitHub | Deploy URL ready |
| Add bot as friend on your phone | QR code from LINE Developers Console |

**Exit criteria:** All credentials in `.env.local`, all infra accounts exist, you can DM your bot (no reply expected yet).

See [`SETUP.md`](./SETUP.md) for the click-by-click walkthrough.

---

### 🟢 Phase 1 — Webhook MVP (4–6 hours)

The foundation. Until this works, nothing else matters.

| Task | Output |
|---|---|
| Implement `webhook/lib/line_verify.py` | Verifies `x-line-signature` against raw body, rejects fake events |
| Implement `webhook/lib/event_parser.py` | Maps LINE event JSON → DB row (Pydantic) |
| Implement `webhook/api/webhook.py` | FastAPI POST handler, returns 200 on success |
| Local test with Cloudflare Tunnel | Webhook URL: `https://<tunnel>.trycloudflare.com/api/webhook` |
| Verify webhook in LINE Developers Console | Console "Verify" button passes |
| Send 5 test messages from your phone | 5 rows in `messages` table |
| Deploy to Vercel | Production webhook URL live |
| Update LINE webhook URL → Vercel URL | Production traffic flowing |

**Exit criteria:** Every message you DM the bot lands in Supabase within 2 seconds. Verified by `select count(*) from messages` and JSONB inspection of `raw` column.

**Don't skip:** Test failure handling. Deploy intentionally broken code, send a message, fix it, redeploy. Should land exactly once due to `message_id unique` + LINE's retries.

---

### 🟢 Phase 2 — Read MCP (4–6 hours)

| Task | Output |
|---|---|
| Implement `mcp/lib/db.py` (asyncpg pool) | Connection works locally |
| Implement `mcp/tools/read.py`: `list_recent_messages` | Returns last N messages, optional `since` filter |
| Implement `mcp/tools/read.py`: `search_messages` | Full-text search via `tsvector` index |
| Implement `mcp/tools/read.py`: `get_conversation` | Thread view by `source_id` |
| Implement `mcp/server.py` | FastMCP wiring, runs as stdio process |
| Add to `claude_desktop_config.json` | Restart Claude Desktop |
| Test 5 different prompts | Claude answers correctly without hallucination |

**Exit criteria:** Claude Desktop can answer 5 different questions about your LINE inbox using only data from the DB.

---

### 🟡 Phase 3 — Reply tools (2–4 hours)

| Task | Output |
|---|---|
| Implement `mcp/lib/line_client.py` | httpx wrapper for `/v2/bot/message/push` and `/v2/bot/profile/{userId}` |
| Implement `mcp/tools/send.py`: `push_message`, `get_profile` | Tool definitions |
| Profile-fetch caching | First lookup writes to `users` table; subsequent calls hit DB |
| Test round-trip | Friend sends → Claude reads → Claude replies → Friend receives |

**Exit criteria:** Full round-trip works. You can ask Claude to triage your inbox and reply in context.

---

### 🟡 Phase 4 — Polish (variable)

Pick what you actually need. Don't do all of it.

- **Media handling:** webhook stores `messageId` only; MCP fetches binary via `/v2/bot/message/{id}/content` on demand. Don't pre-download — saves Supabase storage.
- **Group support:** invite bot to a test LINE group. The webhook already handles `source.type = 'group'`; just verify and add a `list_groups` tool.
- **Semantic search:** add pgvector embeddings on `text_content`. New tool: `semantic_search(query)`. Use local embeddings to stay $0.
- **Token rotation:** Vercel cron (daily) refreshes v2.1 token before 30-day expiry.
- **Dashboard:** Next.js page on Vercel showing recent messages — useful when Claude isn't open.
- **Observability:** alert on webhook 5xx via Vercel monitoring or UptimeRobot.

---

## Risk register

| Risk | Severity | Mitigation |
|---|---|---|
| Webhook downtime → messages lost | 🔴 High | Vercel SLA + UptimeRobot HEAD ping every 5 min |
| Channel access token v2.1 expires (≤30 days) | 🟡 Medium | Calendar reminder month 1, automate in Phase 4 |
| `messageId` collision attack | 🟢 Low | HMAC verification prevents this |
| LINE push rate limit (200/month free) | 🟡 Medium | Monitor; upgrade plan or use replies when possible |
| Supabase free tier limits | 🟢 Low | At 1K msg/month, ~40 years of headroom |
| Private message content leaking | 🔴 High | Supabase project private, service key only in Vercel env vars, single-tenant |
| Reply token expires during Claude reasoning | 🟢 Low | Mitigated by design — using `pushMessage` not `replyMessage` |
| Vercel cold start on first message | 🟡 Medium | ~1–2s extra latency. Live with it or upgrade to Pro for warm functions |

---

## Order of operations for the next session

1. Phase 0 end-to-end (target: 90 minutes)
2. Phase 1 minimum viable webhook returning 200 (target: 2 hours)
3. Phase 1 complete with DB writes (target: 1–2 more hours)

Stop and verify after each. **Don't write Phase 2 until Phase 1's exit criteria are met.** A beautiful MCP that returns zero rows is the most demoralizing failure mode of this project.
