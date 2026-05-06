# MCP Tools

The LINE-MCP exposes five tools to Claude. Two are read-only (Phase 2), three perform actions (Phase 3).

---

## Read tools

### `list_recent_messages`

Returns the most recent messages across all conversations, optionally filtered.

**Inputs:**

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `limit` | int | no | 20 | Max rows. Cap at 200 to keep responses small |
| `since` | ISO datetime | no | null | Only messages after this timestamp |
| `source_id` | string | no | null | Filter to one conversation (user/group) |

**Output:** array of message objects:

```json
{
  "id": 42,
  "source_type": "user",
  "source_id": "U_friend_id",
  "sender_user_id": "U_friend_id",
  "sender_display_name": "Alice",
  "message_type": "text",
  "text": "are you free friday?",
  "timestamp": "2026-05-06T08:30:12+00:00"
}
```

**Example prompt:**
> "What did I get on LINE in the last hour?"

---

### `search_messages`

Full-text search across all stored messages.

**Inputs:**

| Param | Type | Required | Description |
|---|---|---|---|
| `query` | string | yes | Search terms (Postgres tsquery, simplified) |
| `since` | ISO datetime | no | Constrain to recent |
| `until` | ISO datetime | no | Constrain to a window |
| `limit` | int | no | Default 20 |

**Output:** same shape as `list_recent_messages`.

**Example prompt:**
> "Search my LINE for anything mentioning the project deadline."

**Notes:**
- Uses Postgres `tsvector @@ plainto_tsquery('simple', $1)`.
- The `simple` config means no stemming — good for mixed Thai/English content.
- For Thai-aware search, switch to `pg_trgm` indexes (Phase 4).

---

### `get_conversation`

Threaded view of one conversation.

**Inputs:**

| Param | Type | Required | Description |
|---|---|---|---|
| `source_id` | string | yes | userId / groupId / roomId |
| `limit` | int | no | Default 50 |
| `before` | ISO datetime | no | Page backwards from this timestamp |

**Output:** array of message objects, ordered chronologically.

**Example prompt:**
> "Show me the conversation with that user from this morning."

---

## Write tools

### `push_message`

Sends a text message to a user via LINE.

**Inputs:**

| Param | Type | Required | Description |
|---|---|---|---|
| `user_id` | string | yes | Target LINE userId |
| `text` | string | yes | Message body. Max 5000 chars |

**Output:**

```json
{"ok": true, "request_id": "abc123"}
```

**Example prompt:**
> "Reply to Alice saying I'll be 10 minutes late."

**Notes:**
- Counts against the 200 push messages/month free-tier cap.
- Cannot send to a userId who has not added your bot as a friend (LINE returns 403).
- Multimedia, flex messages, stickers: not in v1. Add as separate tools in Phase 4 if needed.

---

### `get_profile`

Fetches a LINE user's profile. Cached in `users` table.

**Inputs:**

| Param | Type | Required | Description |
|---|---|---|---|
| `user_id` | string | yes | LINE userId |
| `force_refresh` | bool | no | Skip cache, fetch fresh (default false) |

**Output:**

```json
{
  "user_id": "U_friend_id",
  "display_name": "Alice",
  "picture_url": "https://...",
  "language": "en",
  "cached_at": "2026-05-06T08:00:00+00:00"
}
```

**Example prompt:**
> "Who is U_abc123?"

**Notes:**
- Cache TTL: ~24 hours. Older lookups auto-refresh.
- Fails (returns null) if the user hasn't added your bot.

---

## Tool design principles

1. **Each tool returns small, structured data.** Claude reasons better over JSON than free-text dumps. Limits default to 20 to keep tokens manageable.
2. **One tool, one job.** No "do everything" mega-tools. Easier for Claude to plan when calls are atomic.
3. **Read tools are pure SELECT.** No side effects. Safe to retry.
4. **Write tools are explicit.** No "auto-reply on Claude's whim." Claude only sends when you ask.
5. **No tools that read LINE directly.** Only the DB. Keeps reads fast and decoupled from LINE API limits.

---

## What's intentionally NOT a tool

- `delete_message`: messages are append-only. If you want to forget, run SQL manually.
- `mark_as_read`: stateful side effects belong in your own UI, not Claude's reasoning.
- `auto_reply`: should be a webhook-time decision, not an MCP tool.
- `summarize_conversation`: that's just a prompt, not a tool. Let Claude do summarization.
- `broadcast_message`: too easy to misuse. If you really need it, add it explicitly with confirmation.
