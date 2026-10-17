import { join } from 'node:path';
import { SendQueue } from '../../src/sender.js';
import { DATA_DIR, getConfig } from '../../src/config.js';
import { command, VoiceReplies } from './engine.js?v=1.1.0';
import { LocalWorker } from './worker.js?v=1.1.0';

let api, engine, worker, previousSend, wrappedSend;
const seenCommands = new Map();

export function setup(value) { api = value; }

export function available() {
  return typeof SendQueue.prototype.sendTextBatch === 'function' && typeof SendQueue.prototype.sendMedia === 'function'
    ? { ok: true } : { ok: false, reason: '当前 QQ Agent 版本缺少统一发送队列接口' };
}

export function activate() {
  if (engine?.active) return;
  worker = new LocalWorker({ config: api.config, dataDir: join(DATA_DIR, 'plugin-data', 'azuma-voice'), log: api.log, warn: api.warn });
  engine = new VoiceReplies({ storage: api.storage, config: api.config,
    audio: (text, signal) => worker.synthesize(text, signal), warn: api.warn,
    dedupeWindow: () => getConfig().send?.dedupeWindowMs ?? 8000 });
  const instance = engine;
  previousSend = SendQueue.prototype.sendTextBatch;
  const original = previousSend;
  // Compatibility adapter for QQ Agent 0.4.8.5, which has no outbound hook.
  // Keep core files intact. Disable/unload restores the exact previous method.
  wrappedSend = function(chatKey, messages, options) { return instance.send(this, original, chatKey, messages, options); };
  SendQueue.prototype.sendTextBatch = wrappedSend;
  if (api.config().autoStart !== false) worker.ensureReady().catch(e => api.warn(`语音服务待就绪：${e.message}`));
  api.log('已启用；默认文字，/voice on 切换当前会话为冬雪莲纯语音');
}

export function deactivate() {
  engine?.dispose(); worker?.stop();
  if (wrappedSend && SendQueue.prototype.sendTextBatch === wrappedSend) SendQueue.prototype.sendTextBatch = previousSend;
  seenCommands.clear();
}
export function dispose() { deactivate(); }

export const hooks = {
  onMessage(ctx) {
    if (!engine?.active) return;
    // Use protocol text segments so @昵称 (including spaces) does not pollute the command.
    const segments = ctx.event?.message;
    const text = Array.isArray(segments) && segments.every(s => ['text', 'at', 'reply'].includes(s.type))
      ? segments.filter(s => s.type === 'text').map(s => s.data?.text || '').join('') : ctx.text;
    const action = command(text);
    if (!action) return;
    // findByMid returns the live store entry in 0.4.8.5. Mark ONLY this control
    // message read, leaving any simultaneous conversation messages untouched.
    // The normal acknowledgement's appendSelf persists the updated store.
    const entry = ctx.store?.findByMid?.(ctx.chatKey, ctx.event?.message_id);
    if (entry) entry.read = true;
    const key = `${ctx.chatKey}:${ctx.event?.message_id ?? text}`;
    const now = Date.now();
    if (now - (seenCommands.get(key) || 0) < 10000) return;
    seenCommands.set(key, now);
    if (seenCommands.size > 500) for (const [k, at] of seenCommands) if (now - at >= 10000) seenCommands.delete(k);
    let reply;
    try {
      if (action === 'on') { engine.setMode(ctx.chatKey, 'voice'); reply = '当前会话已开启冬雪莲纯语音回复。/voice off 恢复文字。'; }
      else if (action === 'off') { engine.setMode(ctx.chatKey, 'text'); reply = '当前会话已恢复文字回复。'; }
      else reply = `当前会话：${engine.isVoice(ctx.chatKey) ? '冬雪莲纯语音' : '文字'}。/voice on 开启语音，/voice off 恢复文字。`;
    } catch (e) { api.warn(`语音模式保存失败：${e.message}`); reply = '语音模式保存失败，本次未切换。'; }
    // Do not hold the 5-second hook while waiting on QQ's send queue.
    Promise.resolve(ctx.send(reply, { azumaTextOnly: true })).catch(e => api.warn(`语音开关确认发送失败：${e.message}`));
  }
};
