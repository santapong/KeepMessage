// MCP server: lets Claude read messages received by server.mjs
import fs from 'node:fs'; import path from 'node:path'; import { fileURLToPath } from 'node:url';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';
const dir = path.dirname(fileURLToPath(import.meta.url));
const INBOX = path.join(dir, 'inbox.jsonl');
const HEARTBEAT = path.join(dir, '.claude-alive');
// env file (same as server.mjs)
const envFile = path.join(dir, 'line-inbox.env');
if (fs.existsSync(envFile)) for (const l of fs.readFileSync(envFile,'utf8').split('\n')) {
  const mm = l.match(/^\s*([A-Z_]+)\s*=\s*(.*)\s*$/); if (mm && !process.env[mm[1]]) process.env[mm[1]] = mm[2];
}
const TOKEN = process.env.CHANNEL_ACCESS_TOKEN || '';
const DEFAULT_USER = process.env.DESTINATION_USER_ID || '';
// heartbeat: while this MCP process lives, Claude counts as online (server.mjs skips auto-reply)
const beat = () => { try { fs.writeFileSync(HEARTBEAT, String(Date.now())); } catch {} };
beat(); setInterval(beat, 30_000).unref();
process.on('exit', () => { try { fs.unlinkSync(HEARTBEAT); } catch {} });
for (const sig of ['SIGINT','SIGTERM','SIGHUP']) process.on(sig, () => process.exit(0));
const load = () => fs.existsSync(INBOX) ? fs.readFileSync(INBOX,'utf8').split('\n').filter(Boolean).map(l=>JSON.parse(l)) : [];
const save = (evs) => fs.writeFileSync(INBOX, evs.map(e=>JSON.stringify(e)).join('\n') + (evs.length?'\n':''));
const summarize = (e) => ({
  id: e.webhookEventId, receivedAt: e.receivedAt, read: e.read, type: e.type,
  from: e.source?.userId, sourceType: e.source?.type, groupId: e.source?.groupId,
  messageType: e.message?.type, text: e.message?.text, messageId: e.message?.id,
  replyToken: e.replyToken, timestamp: e.timestamp, autoReplied: e.autoReplied,
});
const server = new McpServer({ name: 'line-inbox', version: '0.1.0' });
server.tool('get_line_messages', 'Read messages/events received from LINE users via the webhook inbox. Defaults to unread only.',
  { unread_only: z.boolean().default(true), limit: z.number().int().min(1).max(200).default(50), mark_read: z.boolean().default(false) },
  async ({ unread_only, limit, mark_read }) => {
    const all = load(); let sel = unread_only ? all.filter(e => !e.read) : all; sel = sel.slice(-limit);
    if (mark_read && sel.length) { const ids = new Set(sel.map(e=>e.webhookEventId)); save(all.map(e => ids.has(e.webhookEventId) ? {...e, read:true} : e)); }
    return { content: [{ type: 'text', text: JSON.stringify({ count: sel.length, unread_total: all.filter(e=>!e.read).length, events: sel.map(summarize) }, null, 2) }] };
  });
server.tool('ack_line_messages', 'Mark LINE inbox events as read (all unread, or specific event ids).',
  { ids: z.array(z.string()).optional() },
  async ({ ids }) => { const all = load(); const set = ids && new Set(ids); let n=0;
    save(all.map(e => (!e.read && (!set || set.has(e.webhookEventId))) ? (n++, {...e, read:true}) : e));
    return { content: [{ type:'text', text: `marked ${n} as read` }] }; });
server.tool('line_inbox_status', 'Show inbox counts and whether the webhook receiver is running.', {},
  async () => { const all = load(); let up=false; try { up = (await fetch('http://127.0.0.1:18081/health')).ok; } catch {}
    return { content: [{ type:'text', text: JSON.stringify({ receiver_up: up, claude_heartbeat: fs.existsSync(HEARTBEAT), total: all.length, unread: all.filter(e=>!e.read).length, last: all.at(-1)?.receivedAt ?? null }) }] }; });
server.tool('send_line_message', 'Send (push) a text message to a LINE user. Defaults to DESTINATION_USER_ID.',
  { text: z.string().min(1).max(5000), userId: z.string().optional() },
  async ({ text, userId }) => {
    const to = userId || DEFAULT_USER; if (!TOKEN || !to) return { content: [{ type:'text', text: 'CHANNEL_ACCESS_TOKEN / DESTINATION_USER_ID not configured' }], isError: true };
    const r = await fetch('https://api.line.me/v2/bot/message/push', { method:'POST',
      headers: { 'Content-Type':'application/json', Authorization:`Bearer ${TOKEN}` },
      body: JSON.stringify({ to, messages: [{ type:'text', text }] }) });
    return { content: [{ type:'text', text: `${r.status} ${await r.text()}` }], isError: !r.ok };
  });
await server.connect(new StdioServerTransport());
