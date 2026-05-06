# Setup

Step-by-step provisioning of the three external services this project depends on. Total time: 60–90 minutes.

---

## 1. LINE Developers Console (~30 min)

### 1.1 Create an account

1. Go to <https://developers.line.biz/console/>.
2. Log in with your existing LINE account.
3. Agree to the LINE Developers Agreement.

### 1.2 Create a Provider

A provider is a container for your apps/channels.

1. Click **Create new provider**.
2. Name it (e.g., `personal`). Click **Create**.

### 1.3 Create a Messaging API channel

1. Inside your provider, click **Create new channel** → **Messaging API**.
2. Fill in:
   - **Channel name:** anything (e.g., `Personal Inbox`)
   - **Channel description:** anything
   - **Category / Subcategory:** anything
   - **Email:** your email
3. Agree to terms, click **Create**.

### 1.4 Configure the channel

Open the channel you just created.

**Basic settings tab:**
- Copy **Channel Secret** → save as `LINE_CHANNEL_SECRET` in your password manager.

**Messaging API tab:**
- **Channel access token (Channel access token v2.1)** → click **Issue**.
  - Set expiration to 30 days (max).
  - Copy the token → save as `LINE_CHANNEL_ACCESS_TOKEN`.
- **Webhook URL:** leave blank for now (we'll fill in after Vercel deploy).
- **Use webhook:** toggle **ON**.
- **Auto-reply messages:** click **Edit** → in LINE Official Account Manager, **disable** auto-reply.
- **Greeting messages:** **disable** in the same console.

### 1.5 Add the bot as a friend

On the same Messaging API tab, scan the QR code with the LINE app on your phone. Add as friend. (You'll need this to send test messages.)

### 1.6 Get your own user ID (for testing)

The easiest path: send any message to the bot once Phase 1 is deployed and read `sender_user_id` from the first row in `messages`. Save as `DEFAULT_USER_ID` for MCP defaults.

---

## 2. Supabase (~15 min)

### 2.1 Create a project

1. Go to <https://supabase.com/dashboard>.
2. Click **New project**.
3. Fill in:
   - **Name:** `line-mcp`
   - **Database password:** generate a strong one, save it
   - **Region:** closest to LINE's region (Tokyo) for lowest latency — `Northeast Asia (Tokyo)` if available
4. Wait ~2 minutes for provisioning.

### 2.2 Grab credentials

In **Project Settings** → **API**:
- **Project URL** → save as `SUPABASE_URL`
- **service_role secret** → save as `SUPABASE_SERVICE_KEY` (treat like a password — never commit, never use in client code)

In **Project Settings** → **Database**:
- **Connection string** (URI mode, Transaction Pooler) → save as `SUPABASE_DB_URL` (used by asyncpg in the MCP)

### 2.3 Apply the schema

Easiest path — Supabase SQL editor:

1. Open **SQL Editor** in the Supabase dashboard.
2. Paste contents of `db/migrations/001_init.sql`.
3. Click **Run**.

Or via psql:

```bash
psql "$SUPABASE_DB_URL" -f db/migrations/001_init.sql
```

Verify:

```sql
\dt
-- expect: messages, users, bot_state
```

---

## 3. Vercel (~15 min)

### 3.1 Push the repo to GitHub

```bash
git init
git add .
git commit -m "initial scaffold"
gh repo create line-mcp --private --source=. --push
```

### 3.2 Import to Vercel

1. Go to <https://vercel.com/new>.
2. Import your GitHub repo.
3. **Framework preset:** Other.
4. **Root directory:** `webhook` (the webhook lives in this subfolder).
5. **Build & output settings:** leave default.

### 3.3 Set environment variables

In **Project Settings** → **Environment Variables**, add:

| Name | Value |
|---|---|
| `LINE_CHANNEL_SECRET` | from step 1.4 |
| `LINE_CHANNEL_ACCESS_TOKEN` | from step 1.4 |
| `SUPABASE_URL` | from step 2.2 |
| `SUPABASE_SERVICE_KEY` | from step 2.2 |

Apply to **Production**, **Preview**, and **Development**.

### 3.4 Deploy

```bash
vercel --prod
```

Note the deploy URL: `https://<project-name>.vercel.app`.

### 3.5 Wire up the LINE webhook

Back in LINE Developers Console → your channel → Messaging API tab:

- **Webhook URL:** `https://<project-name>.vercel.app/api/webhook`
- Click **Update**.
- Click **Verify** → should return success.

### 3.6 First end-to-end test

1. Open LINE on your phone.
2. Send any text to your bot.
3. In Supabase SQL Editor:
   ```sql
   select id, message_id, text_content, line_timestamp from messages order by id desc limit 5;
   ```
4. You should see the message within ~2 seconds.

If you do — **Phase 1 done.** Move on to Phase 2 (the MCP server).

---

## 4. Local development (Cloudflare Tunnel)

Useful before you deploy to Vercel — iterate on the webhook locally.

```bash
# Install cloudflared
# macOS:  brew install cloudflared
# Linux:  see https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/

# Run your webhook locally
cd webhook
uvicorn api.webhook:app --reload --port 8000

# In another terminal:
cloudflared tunnel --url http://localhost:8000
# → outputs https://<random>.trycloudflare.com
```

Set this URL temporarily as the LINE webhook to test locally. Switch back to Vercel for production.

---

## 5. Claude Desktop wiring

After Phase 2 is built, see [`docs/DEPLOYMENT.md`](./docs/DEPLOYMENT.md#claude-desktop-config) for the `claude_desktop_config.json` snippet.

---

## Common gotchas

| Symptom | Cause | Fix |
|---|---|---|
| LINE "Verify" button fails | Webhook doesn't return 200 quickly enough, or HTTPS cert issue | Check Vercel logs; ensure handler returns before doing heavy work |
| Webhook returns 200 but DB stays empty | HMAC verification rejecting valid requests | Compare `LINE_CHANNEL_SECRET` env var to console; ensure raw body (not parsed) is signed |
| Bot replies "Thanks for adding me!" automatically | Auto-reply or greeting still enabled | Disable in LINE Official Account Manager (step 1.4) |
| `replyToken` errors | Token expired (>60 sec) | Use `pushMessage` instead — already designed in |
| Supabase connection refused | DB URL is the wrong format | Use Transaction Pooler URI, not direct connection |
