import test from 'node:test';
import assert from 'node:assert/strict';
import { command, VoiceReplies } from '../plugins/azuma-voice/engine.js';

function wav() { const b = Buffer.alloc(48); b.write('RIFF'); b.write('WAVE', 8); return b; }
function fixture(audio = async () => wav(), entries = new Map()) {
  const text = [], media = [];
  const storage = { get: (k, d) => entries.has(k) ? entries.get(k) : d, set: (k, v) => entries.set(k, v) };
  const sender = { async sendMedia(...args) { media.push(args); return { message_id: 17 }; } };
  const original = async function(...args) { assert.equal(this, sender); text.push(args); return { sent: [{ text: args[1] }], failed: [] }; };
  const engine = new VoiceReplies({ storage, config: () => ({ maxChars: 600 }), audio });
  return { engine, sender, text, media, entries, send: (key, messages, options) => engine.send(sender, original, key, messages, options) };
}

test('commands accept plain/mentioned input and reject quoted or conversational use', () => {
  for (const s of ['/voice on', '@冬雪莲(QQ:123456) /voice on', '[CQ:at,qq=123456] /voice on']) assert.equal(command(s), 'on');
  assert.equal(command('/voice'), 'status');
  assert.equal(command('/VOICE OFF'), 'off');
  assert.equal(command('我想知道 /voice on 怎么用'), null);
  assert.equal(command('/voice on 你好'), null);
});

test('conversation modes persist, remain independent, and acknowledgements stay text', async () => {
  const f = fixture();
  f.engine.setMode('group:1', 'voice');
  await f.send('private:1', ['文字']);
  await f.send('group:1', ['开关确认'], { azumaTextOnly: true });
  await f.send('group:1', ['你好', '今天过得怎么样？']);
  assert.equal(f.text.length, 2); assert.equal(f.media.length, 1);
  assert.equal(f.media[0][0], 'group:1');
  assert.equal(f.media[0][1][0].type, 'record');
  assert.match(f.media[0][1][0].data.file, /^base64:\/\//);
  assert.match(f.media[0][2].label, /你好 今天过得怎么样/);
  const next = fixture(undefined, f.entries);
  assert.equal(next.engine.isVoice('group:1'), true);
  assert.equal(next.engine.isVoice('group:2'), false);
});

test('repeated voice is deduplicated after success', async () => {
  const f = fixture(); f.engine.setMode('group:1', 'voice');
  const first = await f.send('group:1', '你好');
  const repeat = await f.send('group:1', '你好');
  assert.equal(first.sent[0].messageId, 17);
  assert.equal(repeat.sent[0].deduped, true);
  assert.equal(f.media.length, 1); assert.equal(f.text.length, 0);
});

test('failed TTS falls back without poisoning the next queued reply', async () => {
  let calls = 0;
  const f = fixture(async () => { if (++calls === 1) throw new Error('worker down'); return wav(); });
  f.engine.setMode('group:1', 'voice');
  await f.send('group:1', '第一句'); await f.send('group:1', '第二句');
  assert.equal(f.text.length, 1); assert.equal(f.text[0][1], '第一句'); assert.equal(f.media.length, 1);
});

test('invalid audio, oversized speech, and code-only replies remain text', async () => {
  const f = fixture(async () => Buffer.from('not wav')); f.engine.setMode('group:1', 'voice');
  await f.send('group:1', '你好'); await f.send('group:1', '字'.repeat(601)); await f.send('group:1', '```js\nconst a=1;\n```');
  assert.equal(f.text.length, 3); assert.equal(f.media.length, 0);
});

test('bounded serial queue captures destinations and modes without mixing conversations', async () => {
  let release; const gate = new Promise(resolve => { release = resolve; });
  let busy = 0, maxBusy = 0;
  const f = fixture(async () => { busy++; maxBusy = Math.max(maxBusy, busy); await gate; busy--; return wav(); });
  for (let i = 0; i < 5; i++) f.engine.setMode(`group:${i}`, 'voice');
  const pending = Array.from({ length: 5 }, (_, i) => f.send(`group:${i}`, `内容${i}`));
  f.engine.setMode('group:0', 'text'); release(); await Promise.all(pending);
  assert.equal(maxBusy, 1); assert.equal(f.media.length, 4); assert.equal(f.text.length, 1);
  assert.deepEqual(f.media.map(m => m[0]), ['group:0', 'group:1', 'group:2', 'group:3']);
  assert.equal(f.text[0][0], 'group:4');
});

test('disable aborts ongoing synthesis and leaves no late voice sends', async () => {
  const f = fixture(async (_text, signal) => new Promise((resolve, reject) => signal.addEventListener('abort', () => reject(new Error('aborted')), { once: true })));
  f.engine.setMode('group:1', 'voice'); const pending = f.send('group:1', '你好');
  await new Promise(resolve => setImmediate(resolve)); f.engine.dispose(); await pending;
  assert.equal(f.media.length, 0); assert.equal(f.text.length, 1);
});

test('ambiguous QQ send failure does not cause duplicate text retry', async () => {
  const f = fixture(); f.engine.setMode('group:1', 'voice');
  f.sender.sendMedia = async () => { throw new Error('network timeout after possible delivery'); };
  await assert.rejects(f.send('group:1', '你好'), /network timeout/);
  assert.equal(f.text.length, 0);
});

test('definite pre-send record upload failure falls back once and cools down only its conversation', async () => {
  const f = fixture(); f.engine.setMode('group:1', 'voice'); f.engine.setMode('group:2', 'voice');
  let attempts = 0;
  f.sender.sendMedia = async () => { attempts++; throw new Error('OneBot send_group_msg 失败: retcode=100 highway upload transport failed after 3 attempts (cmdId=1008 chunk=19362/19362 offset=0): Error: read ECONNRESET'); };
  await f.send('group:1', '第一句'); await f.send('group:1', '第二句');
  assert.equal(attempts, 1); assert.equal(f.text.length, 2);
  assert.equal(f.engine.isVoice('group:1'), true);
  await f.send('group:2', '其他群'); assert.equal(attempts, 2);
  f.engine.setMode('group:1', 'voice'); await f.send('group:1', '手动重试');
  assert.equal(attempts, 3);
});

test('record upload resumes automatically after the backoff expires', async () => {
  const f = fixture(); f.engine.setMode('group:1', 'voice');
  f.engine.uploadBackoff.set('group:1', Date.now() - 1);
  await f.send('group:1', '恢复语音');
  assert.equal(f.media.length, 1); assert.equal(f.text.length, 0);
});
