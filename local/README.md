# local/ — working LINE inbox MCP (Node, no cloud)

Went live 23 Aug 2026. Same design as the Python/Vercel/Supabase halves in the parent repo,
collapsed into two files that run on one machine:

| file | role |
|---|---|
| `server.mjs` | webhook receiver on 127.0.0.1:18081 — verifies `X-Line-Signature` (raw-body HMAC), appends events to `inbox.jsonl`, and sends an **offline auto-reply** (via replyToken) only when no Claude session is alive |
| `mcp.mjs` | stdio MCP server — `get_line_messages`, `ack_line_messages`, `line_inbox_status`, `send_line_message`; writes a heartbeat file every 30 s so the receiver knows Claude is online |

## Run
```bash
cp line-inbox.env.example line-inbox.env   # fill CHANNEL_SECRET, CHANNEL_ACCESS_TOKEN, DESTINATION_USER_ID
npm install
node server.mjs &                           # or the systemd user unit below
tailscale funnel --bg 18081                 # public https://<host>.<tailnet>.ts.net/webhook
claude mcp add -s user line-inbox -- node $PWD/mcp.mjs
```
Set the funnel URL as Webhook URL in LINE Developers → Messaging API, enable *Use webhook*, Verify.
Turn OFF *Auto-response messages* in LINE Official Account Manager (the receiver handles offline replies).

systemd user unit (`~/.config/systemd/user/line-inbox.service`):
```ini
[Service]
WorkingDirectory=%h/line-inbox
ExecStart=node %h/line-inbox/server.mjs
Restart=always
[Install]
WantedBy=default.target
```

## Trade-off vs the Vercel/Supabase path
Receives only while this machine is up (inbox is a JSONL file). The parent repo's
webhook→Supabase design is the 24/7 upgrade; the MCP tool surface is the same, so
Claude-side usage doesn't change when you migrate.
