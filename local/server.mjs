// LINE webhook receiver -> appends events to inbox.jsonl
import http from 'node:http';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const dir = path.dirname(fileURLToPath(import.meta.url));
const envFile = path.join(dir, 'line-inbox.env');
if (fs.existsSync(envFile)) for (const l of fs.readFileSync(envFile,'utf8').split('\n')) {
  const m = l.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/); if (m && !process.env[m[1]]) process.env[m[1]] = m[2];
}
const SECRET = process.env.CHANNEL_SECRET || '';
const TOKEN = process.env.CHANNEL_ACCESS_TOKEN || '';
const OFFLINE_REPLY = process.env.OFFLINE_REPLY || 'Claude is offline right now - your message is saved and will be read next session.';
const HEARTBEAT = path.join(dir, '.claude-alive');
const ONLINE_WINDOW_MS = Number(process.env.ONLINE_WINDOW_MS || 90_000);
const claudeOnline = () => { try { return Date.now() - fs.statSync(HEARTBEAT).mtimeMs < ONLINE_WINDOW_MS; } catch { return false; } };
async function replyOffline(ev) {
  if (!TOKEN || !ev.replyToken || ev.type !== 'message') return;
  try {
    const r = await fetch('https://api.line.me/v2/bot/message/reply', { method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${TOKEN}` },
      body: JSON.stringify({ replyToken: ev.replyToken, messages: [{ type: 'text', text: OFFLINE_REPLY }] }) });
    console.error(`offline auto-reply -> ${r.status}`);
  } catch (e) { console.error('offline reply failed', e); }
}
const N8N_FORWARD_URL = process.env.N8N_FORWARD_URL || '';
const N8N_FORWARD_TOKEN = process.env.N8N_FORWARD_TOKEN || '';
async function forwardToN8n(ev) {
  // link-vault: forward text messages containing a URL to the Pi's n8n
  if (!N8N_FORWARD_URL || ev.type !== 'message' || ev.message?.type !== 'text') return;
  if (!/https?:\/\//i.test(ev.message.text || '')) return;
  try {
    const r = await fetch(N8N_FORWARD_URL, { method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-forward-token': N8N_FORWARD_TOKEN },
      body: JSON.stringify(ev) });
    console.error(`n8n forward -> ${r.status}`);
  } catch (e) { console.error('n8n forward failed', e); }
}
const PORT = Number(process.env.PORT || 18081);
const INBOX = path.join(dir, 'inbox.jsonl');
if (!SECRET) console.error('WARNING: CHANNEL_SECRET not set - rejecting all webhooks');

http.createServer((req, res) => {
  res.on('finish', () => console.error(`${new Date().toISOString()} ${req.method} ${req.url} -> ${res.statusCode}`));
  if (req.method === 'GET' && req.url === '/health') { res.end('ok'); return; }
  if (req.method !== 'POST' || !req.url.startsWith('/webhook')) { res.statusCode = 404; res.end(); return; }
  const chunks = []; req.on('data', c => chunks.push(c));
  req.on('end', () => {
    const body = Buffer.concat(chunks);
    const sig = req.headers['x-line-signature'] || '';
    const want = SECRET ? crypto.createHmac('sha256', SECRET).update(body).digest('base64') : null;
    if (!want || sig.length !== want.length || !crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(want))) {
      res.statusCode = 401; res.end('bad signature'); return;
    }
    try {
      const { events = [] } = JSON.parse(body.toString('utf8'));
      const now = new Date().toISOString();
      const online = claudeOnline();
      const seenIds = new Set(fs.existsSync(INBOX) ? fs.readFileSync(INBOX,'utf8').split('\n').filter(Boolean).map(l=>{try{return JSON.parse(l).webhookEventId}catch{return null}}) : []);
      for (const ev of events) {
        if (ev.webhookEventId && seenIds.has(ev.webhookEventId)) { console.error(`dup ${ev.webhookEventId} skipped`); continue; }
        fs.appendFileSync(INBOX, JSON.stringify({ receivedAt: now, read: false, autoReplied: !online, ...ev }) + '\n');
        if (!online) replyOffline(ev);
        forwardToN8n(ev);
      }
      if (events.length) console.error(`${now} stored ${events.length} event(s) (claude ${online ? 'online' : 'offline'})`);
    } catch (e) { console.error('parse error', e); }
    res.end('ok'); // LINE expects 200 quickly
  });
}).listen(PORT, '127.0.0.1', () => console.error(`line-inbox webhook on http://127.0.0.1:${PORT}/webhook`));
