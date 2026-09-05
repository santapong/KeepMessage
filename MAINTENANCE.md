# Maintenance and recovery

Status: **maintained**

Release: **v1.0.0**

Last verified: **2026-09-05**

## Ownership and durable state

The repository owns the receiver and MCP source. It does not own or back up:

- `local/inbox.jsonl` on the Pi;
- the link-vault Postgres database;
- environment files and API credentials;
- Cloudflare tunnel credentials and DNS; or
- systemd user-unit installation and host configuration.

Back up the inbox and link-vault database using the Pi operations backup
workflow. A Git checkout alone cannot recover messages or saved links.

## Verification

Run after code, host, tunnel, token, DNS, Node, n8n, or Postgres changes:

1. Run `npm ci`, `npm audit --omit=dev`, and `node --check` for both scripts in
   `local/`.
2. Confirm `https://line.draveniq.dev/health` returns 200 and `ok`.
3. Confirm unauthenticated `/inbox` returns 401.
4. Send one harmless LINE message and confirm it appears exactly once.
5. Read and acknowledge it through MCP, then send one harmless reply.
6. Send one disposable URL and confirm the link vault stores it once.
7. Confirm the next digest format without exposing message or link contents.

Steps 4–7 are operator acceptance tests and must not be simulated with made-up
evidence.

## Recovery order

1. Check the Pi's `line-inbox` and `cloudflared-line` user services.
2. Check local receiver health on `127.0.0.1:18081`.
3. Check the public health endpoint and Cloudflare tunnel/DNS.
4. Confirm the receiver and MCP use matching API tokens without printing them.
5. Confirm n8n and Postgres only after base message capture works.
6. Restore runtime data from the latest verified Pi backup if required.
7. Use the laptop services as fallback only after disabling the Pi services,
   so two receivers never compete for the same tunnel or webhook.

The detailed commands and known failure modes live in `local/PLAYBOOK.md`.

## Reopen criteria

Change the maintained system only for an incident, security advisory,
provider change, failed recovery exercise, or repeated operator need. The
hosted Python/Vercel/Supabase roadmap and speculative features are not active
commitments.
