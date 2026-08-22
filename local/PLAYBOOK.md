# Playbook — local LINE inbox (state as of 23 Aug 2026, 01:05 ICT)

## Where we parked
- Receiver (`server.mjs`, systemd user unit `line-inbox`) + MCP (`mcp.mjs`, registered as `line-inbox`) work end-to-end: two round-trips proven ("Test" 17:22Z, "Hello" 17:46Z; replies pushed with `send_line_message` / `line-bot`).
- LINE channel **Contractor @896soxdx** (provider `mcp`, channel id 2010934976): Use webhook ON, Webhook redelivery ON, Error statistics ON, OA-Manager auto-response OFF.
- Public ingress was **Tailscale Funnel** `https://santapong.tail5c1b28.ts.net/webhook` — **being retired** (see Failure below). Turn it off: `sudo tailscale funnel off`.
- Next ingress: **Cloudflare Tunnel** → `line.draveniq.dev` (`cloudflared` 2026.8.2 installed at `~/.local/bin/cloudflared`, not yet logged in).

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
