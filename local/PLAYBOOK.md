# Playbook — local LINE inbox (state as of 24 Aug 2026, 14:50 ICT)

## Current state — Cloudflare Tunnel LIVE
- Receiver (`server.mjs`, systemd user unit `line-inbox`) + MCP (`mcp.mjs`, registered as `line-inbox`) work end-to-end; verified again over the new ingress ("Test" 24 Aug 07:48Z stored via line.draveniq.dev).
- LINE channel **Contractor @896soxdx** (provider `mcp`, channel id 2010934976): Use webhook ON, Webhook redelivery ON, Error statistics ON, OA-Manager auto-response OFF. Webhook URL = `https://line.draveniq.dev/webhook` (console Verify: Success, 24 Aug 2026).
- Public ingress: **Cloudflare Tunnel** `line-inbox` (UUID `dad40729-b8dd-4743-a2b6-42a3e97fdd26`), config `~/.cloudflared/config.yml` → `http://127.0.0.1:18081`, systemd user unit `cloudflared-line.service` (enabled, Restart=always). CNAME `line.draveniq.dev` → tunnel.
- Old **Tailscale Funnel** ingress retired — ensure it's off: `sudo tailscale funnel off` (user).

## Failure we hit (keep this)
Messages stopped arriving while every local check passed (signed POST via public URL → 200, LINE console Verify → 200, LINE `POST /v2/bot/channel/webhook/test` → 200).
LINE Developers → channel → **Webhook errors** showed the truth: `could_not_connect — Unknown host: https://santapong.tail5c1b28.ts.net/webhook`.
LINE's *event-delivery* fleet intermittently cannot DNS-resolve `*.ts.net`; the console/test path resolves it fine, so those checks are misleading.
Lesson: **turn on Error statistics aggregation first** and read that page before debugging the receiver. Redelivery ON + `webhookEventId` dedupe makes transient failures self-heal.

## Resume steps (Cloudflare Tunnel)
1. `cloudflared tunnel login` (user; pick zone draveniq.dev)
2. `cloudflared tunnel create line-inbox` → note tunnel UUID, creds at `~/.cloudflared/<uuid>.json`
3. `cloudflared tunnel route dns line-inbox line.draveniq.dev`
4. `~/.cloudflared/config.yml`:
   ```yaml
   tunnel: <uuid>
   credentials-file: /home/santapong/.cloudflared/<uuid>.json
   ingress:
     - hostname: line.draveniq.dev
       service: http://127.0.0.1:18081
     - service: http_status:404
   ```
5. systemd user unit `cloudflared-line.service`: `ExecStart=%h/.local/bin/cloudflared tunnel run line-inbox`, `Restart=always`, enable --now
6. `curl https://line.draveniq.dev/health` → ok, then LINE Developers → Messaging API → Webhook URL = `https://line.draveniq.dev/webhook` → Update → Verify
7. Send a test message; `journalctl --user -u line-inbox -f` should show `POST /webhook -> 200` + `stored 1 event(s)`
8. `sudo tailscale funnel off`

## Debug checklist (fast path)
| symptom | check |
|---|---|
| no events | LINE console → Webhook errors page (reason/detail) |
| 401 in receiver log | CHANNEL_SECRET wrong / env not loaded (`systemctl --user restart line-inbox`) |
| auto-reply fires while Claude open | no `.claude-alive` heartbeat → MCP not loaded in that session (restart Claude Code) |
| public URL 000 from this laptop | hairpin quirk; test with `--resolve host:443:<ingress ip>` or from another network |

## Blocked-for-Claude actions (auto-mode classifier)
`tailscale funnel`, `git push`, GitHub form submits, `rm -rf`, sudo — hand to the user as `! <cmd>`.

## Link Vault (added 24 Aug 2026)
Links sent to the OA are auto-saved, categorized, and come back as a daily LINE digest.

Flow: LINE → line.draveniq.dev → server.mjs → `forwardToN8n()` (text msgs containing http(s) only, header `x-forward-token` = `N8N_FORWARD_TOKEN`) → Pi n8n webhook `https://santapong-dev.tail5c1b28.ts.net/webhook/line-link` → workflow **LINE Link Saver** (ID `LinkSaverLine001`): extract URLs + `#category` hashtag override → fetch title/og (fail-soft) → rule-based category (video/social/paper/code/robotics/learning/ai/inbox) → INSERT into Postgres.

Store: DB `linkvault`, table `links` (url UNIQUE, title, summary, category, status unread|read|archived) in the Pi's pgvector container; user `linkvault` (password in `line-inbox.env.local-notes`, gitignored). NOTE: new DBs there must use `TEMPLATE template0` (template1 has a collation version mismatch).

Digest: workflow **Daily Link Digest** (ID `DailyLinkDigest1`), cron 0 8 * * * Asia/Bangkok → SELECT unread → grouped message → LINE push. Links stay in the digest until marked read/archived (via a Claude session: `UPDATE links SET status='read' WHERE id=...`).

Ops notes:
- Workflows/credentials were imported via CLI (`docker exec n8n n8n import:workflow|import:credentials`, then `publish:workflow --id=...` + `docker restart n8n`). Webhook nodes NEED a `webhookId` uuid or activation silently skips registration ("unknown webhook").
- Credential ids: `linkvaultpg01` (postgres), `linelinkfwd01` (x-forward-token), `linepushtok01` (LINE Bearer).
- server.mjs env parser now accepts digits in var names (`[A-Z0-9_]+`).
- Docker containers on the Pi use explicit DNS 1.1.1.1/8.8.8.8 (`/etc/docker/daemon.json`) — the router's DNS SERVFAILs from Docker's forwarder; symptom was "The DNS server returned an error" on api.line.me.
- Pi host nginx (Serve→8080) died 18 Aug because `/var/log/nginx` was deleted; fix `sudo mkdir -p /var/log/nginx && sudo systemctl start nginx`. All n8n webhooks 502 when it's down.

## Receiver moved to the Pi (24 Aug 2026, evening)
Capture is now 24/7 — the laptop is out of the ingress path entirely.
- Pi runs BOTH: `~/line-inbox-svc/server.mjs` (systemd user `line-inbox`, node 20 via apt) and `cloudflared-line` (same tunnel UUID, creds copied to Pi `~/.cloudflared/`). Laptop's `line-inbox` + `cloudflared-line` user units are disabled (they remain as instant fallback: disable Pi units, re-enable laptop ones).
- server.mjs v2 adds a token-authed remote API on the same port: `GET /inbox`, `POST /ack`, `POST /heartbeat` (header `x-api-token` = `API_TOKEN` in the Pi env). mcp.mjs v2 (laptop) talks to it via `INBOX_API_URL=https://line.draveniq.dev` + `INBOX_API_TOKEN` — no local inbox file any more.
- n8n forward is now Pi-local: `N8N_FORWARD_URL=http://127.0.0.1:8080/webhook/line-link` (through host nginx; no ts.net DNS dependency).
- Pi user journald keeps no history (`journalctl --user` empty) — read logs with `systemctl --user status line-inbox`.
- Duplicate links are silently deduped by the vault's UNIQUE(url) — resending a link is a no-op by design.
