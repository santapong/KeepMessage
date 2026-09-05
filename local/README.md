# `local/` — live Pi LINE inbox

This is the production implementation of KeepMessage.

| File | Role |
|---|---|
| `server.mjs` | Pi service on `127.0.0.1:18081`: verifies LINE signatures, deduplicates and stores events, exposes the token-authenticated inbox API, sends offline replies, and forwards URL messages to n8n. |
| `mcp.mjs` | Local stdio MCP client: reads/acks the remote inbox, reports status, sends LINE messages, and refreshes the heartbeat. |

## Configuration

```bash
cp line-inbox.env.example line-inbox.env
npm ci
```

The receiver requires `CHANNEL_SECRET` and `API_TOKEN`. Sending requires
`CHANNEL_ACCESS_TOKEN`; the MCP client uses `INBOX_API_URL` and
`INBOX_API_TOKEN`. Link-vault forwarding is optional and remains off when
`N8N_FORWARD_URL` is empty.

`line-inbox.env`, `inbox.jsonl`, `.claude-alive`, `node_modules`, and
`*.local-notes` are ignored. Keep every real value and all message data out of
Git.

## Live topology

- The Pi runs systemd user services `line-inbox` and `cloudflared-line`.
- Cloudflare routes `line.draveniq.dev` to the receiver.
- The laptop runs only `mcp.mjs`; it is no longer part of webhook ingress.
- The Pi receiver forwards URL-bearing messages to Pi-local n8n.

Use [PLAYBOOK.md](PLAYBOOK.md) for exact service, recovery, and link-vault
operations. Do not re-enable the older Tailscale Funnel path while the
Cloudflare path is healthy.

## Safe checks

```bash
npm ci
npm audit --omit=dev
node --check server.mjs
node --check mcp.mjs
curl -fsS https://line.draveniq.dev/health
```

The health endpoint returns only `ok`. Do not place API tokens in command
history, screenshots, issues, or committed scripts.
