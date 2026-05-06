---
name: setup-status
description: Audits Phase 0 readiness for LINE-MCP — checks .env completeness, Supabase reachability, schema applied, webhook live, and reports what is still blocking. Invoke when the user asks "where are we?", "what's left?", "am I ready to deploy?", or runs /setup-status.
---

# Setup status audit

Goal: produce a one-screen report of which Phase 0 / Phase 1 prerequisites are satisfied and which are blocking. Be specific — name the missing variable, the unreachable service, the unapplied migration.

## Steps

Run these in parallel where possible. **Do not** print secret values; only "set" / "unset".

### 1. Local environment

- Check `.env` exists in repo root. If missing, point user at [.env.example](../../.env.example).
- For each of `LINE_CHANNEL_SECRET`, `LINE_CHANNEL_ACCESS_TOKEN`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_DB_URL`, `DEFAULT_USER_ID`: report set/unset (do not echo values).
- Verify `SUPABASE_DB_URL` uses port `6543` (transaction pooler). Flag if it uses `5432` — direct connections exhaust quickly.

### 2. Supabase reachability

If `SUPABASE_DB_URL` is set, attempt a no-op query:

```bash
psql "$SUPABASE_DB_URL" -c "select 1" -tA
```

Report: reachable / auth failed / network unreachable.

### 3. Schema applied

If reachable, check the three expected tables exist:

```bash
psql "$SUPABASE_DB_URL" -tAc "select tablename from pg_tables where schemaname='public' and tablename in ('messages','users','bot_state') order by tablename"
```

If fewer than 3 rows, the migration has not been applied. Suggest:

```bash
psql "$SUPABASE_DB_URL" -f db/migrations/001_init.sql
```

### 4. Message volume

If `messages` exists, report row count:

```bash
psql "$SUPABASE_DB_URL" -tAc "select count(*) from messages"
```

Zero rows + Phase 1 supposed-deployed = webhook is not actually receiving traffic. Investigate before claiming Phase 1 done.

### 5. Webhook deploy state

- Check `git log --oneline -5` and `git remote get-url origin`.
- Check for `.vercel/` directory (means `vercel link` has been run).
- If a Vercel URL is known (ask the user, do not guess), `curl -sS -o /dev/null -w "%{http_code}\n" https://<url>/api/webhook` — expect 200 from the GET health endpoint.

### 6. LINE channel state

Cannot verify from here without making an authenticated API call. Ask the user to confirm:
- Webhook URL set in LINE Developers Console points at the Vercel deploy
- "Use webhook" toggle is on
- Auto-reply and greeting messages are off

## Output format

Single status block, no preamble. Example:

```
Phase 0 status

env:        4/5 set (missing: LINE_CHANNEL_ACCESS_TOKEN)
supabase:   reachable, schema applied (3/3 tables), 0 rows in messages
vercel:     not linked (.vercel/ missing)
line:       cannot verify — confirm webhook URL + toggles in console

Blocking next: paste LINE_CHANNEL_ACCESS_TOKEN into .env, then run vercel link.
```

Then a single sentence on what to do next. Stop. Do not continue with deploy steps unless the user asks.
