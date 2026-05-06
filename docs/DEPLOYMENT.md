# Deployment

## 1. Webhook → Vercel

### Project structure

The `webhook/` directory is the Vercel project root. It contains a single Python serverless function exposed at `/api/webhook`.

```
webhook/
├── api/
│   └── webhook.py          # FastAPI app — Vercel routes to this
├── lib/
│   ├── line_verify.py      # HMAC verification
│   ├── event_parser.py     # event JSON → DB row
│   └── db.py               # Supabase client
├── requirements.txt
└── vercel.json             # routing config
```

### vercel.json

```json
{
  "version": 2,
  "builds": [
    { "src": "api/webhook.py", "use": "@vercel/python" }
  ],
  "routes": [
    { "src": "/api/webhook", "dest": "api/webhook.py" }
  ]
}
```

### requirements.txt

```
fastapi==0.115.0
line-bot-sdk==3.11.0
supabase==2.7.4
pydantic==2.9.0
```

### Environment variables

Set in Vercel **Project Settings → Environment Variables**:

| Variable | Source |
|---|---|
| `LINE_CHANNEL_SECRET` | LINE Console → Basic settings |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Console → Messaging API tab |
| `SUPABASE_URL` | Supabase → API |
| `SUPABASE_SERVICE_KEY` | Supabase → API (service_role) |

Apply to **Production**, **Preview**, **Development**.

### Deploy

```bash
cd webhook
vercel --prod
```

Or push to `main` and let auto-deploy handle it (recommended after initial setup).

### Wire LINE webhook

LINE Developers Console → your channel → Messaging API tab:
- **Webhook URL:** `https://<your-project>.vercel.app/api/webhook`
- **Use webhook:** ON
- Click **Verify** → success.

---

## 2. Database → Supabase

Schema lives in `db/migrations/001_init.sql`. Apply once via:

**Option A — Supabase SQL editor:**
Paste contents, click **Run**.

**Option B — psql:**
```bash
psql "$SUPABASE_DB_URL" -f db/migrations/001_init.sql
```

**Option C — Supabase CLI (if you adopt it later):**
```bash
supabase db push
```

Verify:
```sql
\dt
-- expect: messages, users, bot_state
\d messages
-- verify columns and indexes
```

---

## 3. MCP → local + Claude Desktop

### Project structure

```
mcp/
├── server.py               # FastMCP entrypoint
├── tools/
│   ├── read.py             # list_recent, search, get_conversation
│   └── send.py             # push_message, get_profile
├── lib/
│   ├── line_client.py      # httpx wrapper
│   └── db.py               # asyncpg pool
└── pyproject.toml
```

### Install dependencies

Recommended: `uv` for speed.

```bash
cd mcp
uv venv
uv pip install -e .
```

Or with stock pip:
```bash
cd mcp
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Local env

Create `mcp/.env`:

```
LINE_CHANNEL_ACCESS_TOKEN=...
SUPABASE_DB_URL=postgresql://postgres:...@...supabase.co:6543/postgres
DEFAULT_USER_ID=U_your_user_id        # optional, used as default for push_message
```

### Test locally before wiring to Claude Desktop

```bash
# Run with the MCP Inspector
npx @modelcontextprotocol/inspector uv run mcp/server.py
```

Open the inspector URL, manually call each tool, verify results.

### Claude Desktop config

Edit `claude_desktop_config.json`:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux** (community build): `~/.config/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

Add:

```json
{
  "mcpServers": {
    "line-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/line-mcp/mcp",
        "run",
        "server.py"
      ],
      "env": {
        "LINE_CHANNEL_ACCESS_TOKEN": "...",
        "SUPABASE_DB_URL": "postgresql://...",
        "DEFAULT_USER_ID": "U_your_user_id"
      }
    }
  }
}
```

Restart Claude Desktop. The tools should appear in the tool picker.

### Verify

Ask Claude:
- "What tools do you have available?"
- "List my recent LINE messages."

If tools don't appear, check:
- Path in `--directory` is absolute and correct
- `uv` is on PATH (or use full path: `/usr/local/bin/uv`)
- Restart Claude Desktop fully (quit, not just close window)
- Check Claude Desktop logs

---

## 4. CI / CD (optional, Phase 4)

### GitHub Actions — webhook tests

`.github/workflows/test.yml`:

```yaml
name: test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r webhook/requirements.txt -r mcp/requirements-dev.txt
      - run: pytest
```

### Vercel auto-deploy

Default Vercel behavior: every push to `main` deploys to production. Push to other branches creates preview deploys with separate URLs (set up a separate LINE channel for preview testing if you want this).

---

## 5. Operational concerns

### Token rotation

Channel access tokens v2.1 expire after up to 30 days. Set a calendar reminder month 1.

Manual rotation:
1. LINE Console → Messaging API tab → **Issue new token**.
2. Update `LINE_CHANNEL_ACCESS_TOKEN` in Vercel + your local MCP `.env`.
3. Redeploy webhook (`vercel --prod` or push).
4. Restart Claude Desktop to reload MCP env.
5. Revoke old token in LINE Console.

Automate in Phase 4 with a Vercel cron.

### Monitoring

Cheap signals:
- **Vercel dashboard:** function invocations, error rate
- **UptimeRobot:** HEAD ping `/api/webhook` every 5 min, alert on 5xx
- **Supabase dashboard:** row count over time, query latency

Daily sanity check via SQL:
```sql
select date_trunc('hour', line_timestamp) as hour, count(*)
from messages
where line_timestamp > now() - interval '24 hours'
group by 1 order by 1;
```

If a row drops to zero unexpectedly, the webhook is down.

### Backup

Supabase free tier auto-backups for 7 days. Enough for personal use.

For peace of mind:
```bash
pg_dump "$SUPABASE_DB_URL" > backup-$(date +%Y%m%d).sql
```
Run weekly via a cron on your machine.
