-- LINE-MCP — initial schema
-- Apply via: psql "$SUPABASE_DB_URL" -f db/migrations/001_init.sql
-- Or paste into Supabase SQL Editor and Run.

-- ============================================================================
-- messages: every LINE webhook event with type='message' becomes a row
-- ============================================================================
create table if not exists messages (
  id                bigserial primary key,
  message_id        text unique,           -- LINE message.id (idempotency)
  webhook_event_id  text,                  -- LINE event.webhookEventId
  source_type       text not null,         -- 'user' | 'group' | 'room'
  source_id         text not null,         -- userId / groupId / roomId
  sender_user_id    text,                  -- can differ from source in groups
  message_type      text not null,         -- 'text' | 'image' | 'sticker' | 'audio' | 'video' | 'file' | 'location'
  text_content      text,                  -- denormalized text for fast search; null if non-text
  raw               jsonb not null,        -- full event payload (forward-compat)
  line_timestamp    timestamptz not null,  -- LINE's authoritative timestamp
  created_at        timestamptz not null default now()
);

create index if not exists messages_source_time
  on messages (source_id, line_timestamp desc);

create index if not exists messages_time
  on messages (line_timestamp desc);

create index if not exists messages_text_fts
  on messages using gin (to_tsvector('simple', coalesce(text_content, '')));

comment on table messages is 'Inbound LINE messages captured by the webhook';
comment on column messages.raw is 'Full event JSON for forward compatibility and replay';
comment on column messages.text_content is 'Denormalized from raw for indexable full-text search';

-- ============================================================================
-- users: cache of LINE profile lookups
-- ============================================================================
create table if not exists users (
  user_id       text primary key,         -- LINE userId
  display_name  text,
  picture_url   text,
  language      text,
  fetched_at    timestamptz not null default now()
);

comment on table users is 'Profile cache; refreshed on demand by MCP';

-- ============================================================================
-- bot_state: generic key-value store for cursors, dedup, last-seen markers
-- ============================================================================
create table if not exists bot_state (
  key         text primary key,
  value       jsonb not null,
  updated_at  timestamptz not null default now()
);

comment on table bot_state is 'Bot-level metadata: token expiry, last event time, etc.';
