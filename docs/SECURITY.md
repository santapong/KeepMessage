# Security

## Threat model

### Assets
- LINE messages (potentially private content from friends)
- LINE channel access token (allows sending as your bot)
- LINE channel secret (allows forging webhook events if leaked)
- Supabase service key (allows full DB access)

### Adversaries
- **Random internet attackers** posting to your webhook
- **Anyone who steals secrets from a leaked `.env`** or compromised dev machine
- **Compromised dependencies** (supply chain)

This is a personal-scale project. We are not modeling nation-state actors.

---

## Critical controls

### 1. HMAC verification at the webhook

**This is the single most important control.** Without it, anyone on the internet can POST fake messages to your webhook URL and pollute your DB.

LINE signs every webhook request with HMAC-SHA256 over the raw body, using your channel secret. The signature arrives in the `X-Line-Signature` header.

```python
import hmac, hashlib, base64

def verify(raw_body: bytes, signature_header: str, channel_secret: str) -> bool:
    expected = base64.b64encode(
        hmac.new(channel_secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
    ).decode("utf-8")
    return hmac.compare_digest(expected, signature_header)
```

**Critical implementation notes:**
- Use the **raw** body bytes, not the parsed JSON. Re-serializing changes whitespace and breaks signatures.
- Use `hmac.compare_digest`, not `==`. Constant-time comparison prevents timing attacks.
- Reject (HTTP 401) on mismatch and **don't log the body** of rejected requests — could be attacker probes.

In FastAPI, read raw body before any middleware parses it:

```python
from fastapi import FastAPI, Request, HTTPException

@app.post("/api/webhook")
async def webhook(request: Request):
    raw = await request.body()
    sig = request.headers.get("x-line-signature", "")
    if not verify(raw, sig, CHANNEL_SECRET):
        raise HTTPException(401)
    # ... parse and store ...
```

### 2. Secret management

| Secret | Where it lives | Where it must NOT live |
|---|---|---|
| `LINE_CHANNEL_SECRET` | Vercel env vars, local `.env` | Repo, client-side code, logs |
| `LINE_CHANNEL_ACCESS_TOKEN` | Vercel env vars, MCP local env | Repo, client-side code, logs |
| `SUPABASE_SERVICE_KEY` | Vercel env vars, MCP local env | Repo, browser, public APIs |
| `SUPABASE_DB_URL` | MCP local env | Repo |

**Rules:**
- `.env` is gitignored. Verify before every commit (`git status` checks).
- Never `print()` secrets, even in development.
- Rotate immediately if a secret is exposed:
  - LINE channel access token: re-issue in console
  - Channel secret: contact LINE — **cannot be rotated easily**, treat as long-lived
  - Supabase service key: rotate in Supabase dashboard

### 3. Token rotation

Channel access tokens v2.1 expire after up to 30 days. Plan for rotation:

- **Phase 0–3:** Manual. Calendar reminder. Re-issue, update Vercel env, redeploy.
- **Phase 4:** Automate via Vercel cron — JWT-based refresh against LINE's auth API.

The long-lived token alternative is tempting but discouraged. If it leaks, anyone can impersonate your bot indefinitely.

### 4. Database access scoping

**Supabase configuration:**
- Project is private (default).
- Service key used only by webhook (Vercel env) and MCP (your local `.env`).
- Anon key is **not used** anywhere. Disable it if possible.
- Row-level security (RLS) is **not enabled** for single-tenant. If multi-tenant, enforce RLS by `tenant_id`.

### 5. Network exposure

- Webhook is public HTTPS at `<vercel-app>.vercel.app`. Anyone can hit it. Defense is HMAC verification (control #1).
- MCP runs on localhost only via stdio. Not network-accessible.
- Supabase is reachable over the internet via TLS. Auth via service key.

---

## Less-critical but worth doing

### Webhook returns minimal information

Don't return debugging info to LINE on errors. Return:
- `200 OK` on success
- `401` on signature failure
- `500` on internal error (with no body)

Verbose errors leak implementation details. Keep them in Vercel logs.

### Don't log message content

Vercel logs persist for ~7 days. Logging `text_content` means private messages are recoverable from your Vercel dashboard.

```python
# DON'T:
print(f"Got message: {event.message.text}")

# DO:
print(f"Got message id={event.message.id} type={event.message.type}")
```

### Pin dependencies

Use `requirements.txt` with exact versions:
```
fastapi==0.115.0
line-bot-sdk==3.11.0
supabase==2.7.4
```

Renovate or Dependabot for managed updates.

### Audit log for sends

Every `push_message` call writes to `bot_state` (or a dedicated `outbound_log` table) with timestamp, target, and text length. Lets you see "what did Claude send?" later.

---

## Privacy considerations

You are running a personal LINE bot. People who message it are sending you messages, with implicit consent that you'll see them.

**They are NOT consenting to:**
- Their messages being processed by an LLM
- Their messages being stored in your database
- Their profiles being cached

Your obligations depend on jurisdiction. Some practical steps:
- If you intend to use this for anyone other than yourself: post a privacy notice in your bot's profile / first-message greeting.
- If anyone asks, delete their data on request: `DELETE FROM messages WHERE sender_user_id = $1; DELETE FROM users WHERE user_id = $1;`
- Keep the system single-user until you've thought through this for any wider scope.

---

## What to do if something leaks

| Leaked secret | Severity | Action |
|---|---|---|
| `LINE_CHANNEL_ACCESS_TOKEN` | 🔴 Anyone can send as your bot | Revoke in console, issue new one, update Vercel + MCP envs |
| `LINE_CHANNEL_SECRET` | 🟡 Anyone can forge webhook events; must be re-issued through LINE support | Rotate via console (re-create channel if needed); review DB for spurious rows |
| `SUPABASE_SERVICE_KEY` | 🔴 Full DB read/write/delete | Rotate in Supabase, update Vercel + MCP envs, audit `bot_state` for tampering |
| `SUPABASE_DB_URL` (just the connection string, no separate password) | 🟡 If host:port:db are leaked but service key isn't, attacker can't auth | Treat as low-severity but rotate password on principle |
| `.env` committed to GitHub | 🔴 All secrets compromised | Rotate everything; use `git filter-repo` to scrub; force-push; assume the repo is forever-tainted |
