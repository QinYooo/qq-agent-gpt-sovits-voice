import { createHash } from 'node:crypto';

export function command(text) {
  // QQ Agent expands mentions to @昵称(QQ:123); accept a leading mention only.
  const clean = String(text || '').trim()
    .replace(/^(?:\[CQ:at,qq=\d+\]\s*|@[^\r\n]*?\(QQ:\d+\)\s*|@\d+\s+)+/, '').trim();
  const match = /^\/voice(?:\s+(on|off|status))?$/i.exec(clean);
  return match ? (match[1]?.toLowerCase() || 'status') : null;
}

export function speechText(text) {
  return String(text).replace(/```[\s\S]*?```/g, '')
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/https?:\/\/\S+/g, '').replace(/<[^>]+>/g, '')
    .replace(/^\s*#{1,6}\s+/gm, '').replace(/[*_`|]/g, '')
    .replace(/\s+/g, ' ').trim();
}

export class VoiceReplies {
  constructor({ storage, config, audio, warn = () => {}, dedupeWindow = () => 8000 }) {
    this.storage = storage;
    this.config = config;
    this.audio = audio;
    this.warn = warn;
    this.dedupeWindow = dedupeWindow;
    this.active = true;
    this.pending = 0;
    this.queue = Promise.resolve();
    this.recent = new Map();
    this.uploadBackoff = new Map();
    this.controller = new AbortController();
  }

  isVoice(chatKey) { return this.storage.get(`mode:${chatKey}`, 'text') === 'voice'; }
  setMode(chatKey, value) {
    this.storage.set(`mode:${chatKey}`, value);
    this.uploadBackoff.delete(chatKey);
  }
  dispose() { this.active = false; this.controller.abort(); }

  async send(sender, original, chatKey, messages, options = {}) {
    const sendText = (items = messages) => original.call(sender, chatKey, items, options);
    if (!this.active || options.azumaTextOnly || !this.isVoice(chatKey)) return sendText();
    if (Date.now() < (this.uploadBackoff.get(chatKey) || 0)) return sendText();
    const text = speechText((Array.isArray(messages) ? messages : [messages]).map(m => String(m ?? '')).join('\n'));
    const maxChars = Math.max(1, Math.min(600, Number(this.config().maxChars) || 600));
    if (!text || Array.from(text).length > maxChars) return sendText();
    if (this.pending >= 4) {
      this.warn('语音队列已满，本次回退文字');
      return sendText();
    }
    const fingerprint = createHash('sha256').update(`${chatKey}\n${text}`).digest('hex');
    // Capture this turn's mode now. Later /voice changes affect subsequent sends.
    this.pending++;
    const task = this.queue.then(async () => {
      if (!this.active) return sendText();
      if (Date.now() < (this.uploadBackoff.get(chatKey) || 0)) return sendText();
      const duplicate = () => options.dedupe !== false && Number(this.dedupeWindow()) > 0
        && Date.now() - (this.recent.get(fingerprint) || 0) < Number(this.dedupeWindow());
      if (duplicate()) return { sent: [{ text, messageId: null, deduped: true }], failed: [] };
      let wav;
      try {
        wav = await this.audio(text, this.controller.signal);
        if (wav.length < 44 || wav.length > 20 * 1024 * 1024
          || wav.toString('ascii', 0, 4) !== 'RIFF' || wav.toString('ascii', 8, 12) !== 'WAVE') {
          throw new Error('语音服务未返回有效 WAV');
        }
      } catch (error) {
        this.warn(`语音合成失败，回退文字：${error?.message || error}`);
        return sendText();
      }
      if (!this.active) return sendText();
      // sendMedia preserves the core whitelist, rate limits and self history.
      // SnowLuma converts WAV to SILK. Inline data avoids Windows path issues.
      let data;
      try {
        data = await sender.sendMedia(chatKey, [
          { type: 'record', data: { file: `base64://${wav.toString('base64')}` } }
        ], { label: `[冬雪莲语音] ${text}`, dedupeKey: `azuma:${fingerprint}:${Date.now()}` });
      } catch (error) {
        // SnowLuma throws this exact error while building/uploading the record,
        // before MessageApi.sendGroup/sendPrivate is called: no QQ message exists.
        // A generic HTTP/QQ timeout is ambiguous and must still propagate.
        const message = String(error?.message || error);
        if (!/highway upload transport failed after \d+ attempts \(cmdId=100[78]\b/.test(message)) throw error;
        this.uploadBackoff.set(chatKey, Date.now() + 120000);
        if (this.uploadBackoff.size > 500) {
          const now = Date.now();
          for (const [key, until] of this.uploadBackoff) if (until <= now) this.uploadBackoff.delete(key);
        }
        this.warn('QQ 语音上传明确失败，本次回退原文字；该会话暂停语音上传 2 分钟，/voice on 可立即重试');
        return sendText();
      }
      if (options.dedupe !== false) this.recent.set(fingerprint, Date.now());
      if (this.recent.size > 500) {
        const now = Date.now();
        for (const [key, at] of this.recent) if (now - at > Math.max(8000, Number(this.dedupeWindow()) || 0)) this.recent.delete(key);
        while (this.recent.size > 500) this.recent.delete(this.recent.keys().next().value);
      }
      return { sent: [{ text, messageId: data?.message_id ?? null, at: new Date().toLocaleTimeString('zh-CN', { hour12: false }), kind: 'voice' }], failed: [] };
    }).finally(() => { this.pending--; });
    this.queue = task.catch(() => {});
    return task;
  }
}
