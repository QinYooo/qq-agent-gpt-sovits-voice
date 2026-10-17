import http from 'node:http';
import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, openSync, closeSync } from 'node:fs';
import { join, isAbsolute } from 'node:path';

// A trusted local bridge with a fixed destination, independent of web-fetch policy.
// No URL from a QQ message is ever accepted here; redirects are never followed.
export function localRequest(path, { text, timeoutMs = 1500, signal } = {}) {
  return new Promise((resolve, reject) => {
    const body = text === undefined ? undefined : Buffer.from(JSON.stringify({ text }));
    const req = http.request({ hostname: '127.0.0.1', port: 9881, path,
      method: body ? 'POST' : 'GET', signal,
      headers: body ? { 'Content-Type': 'application/json', 'Content-Length': body.length } : {}
    }, res => {
      const chunks = []; let size = 0;
      res.on('data', chunk => {
        size += chunk.length;
        if (size > 20 * 1024 * 1024) { res.destroy(); req.destroy(new Error('语音响应超过 20MB')); }
        else chunks.push(chunk);
      });
      res.on('error', reject);
      res.on('aborted', () => reject(new Error('语音响应中断')));
      res.on('end', () => res.statusCode === 200 ? resolve(Buffer.concat(chunks)) : reject(new Error(`TTS HTTP ${res.statusCode}`)));
    });
    const timer = setTimeout(() => req.destroy(new Error('本地语音服务响应超时')), timeoutMs);
    timer.unref?.();
    req.once('close', () => clearTimeout(timer));
    req.on('error', reject);
    req.end(body);
  });
}

export function configuredDirectory(config) {
  const dir = String(config.sovitsDir || '').trim();
  if (!dir || !isAbsolute(dir)) throw new Error('请在插件设置中填写语音项目的绝对路径');
  return dir;
}

export function pythonPath(dir, platform = process.platform) {
  return platform === 'win32' ? join(dir, '.venv', 'Scripts', 'python.exe') : join(dir, '.venv', 'bin', 'python');
}

export class LocalWorker {
  constructor({ config, dataDir, log = () => {}, warn = () => {} }) {
    this.config = config; this.dataDir = dataDir; this.log = log; this.warn = warn;
    this.child = null; this.starting = null; this.stopped = false;
    this.abort = new AbortController();
  }
  async healthy() {
    const health = JSON.parse((await localRequest('/health', { signal: this.abort.signal })).toString('utf8'));
    if (health.ready !== true || health.voice !== 'azuma-v2Pro') throw new Error('9881 端口不是冬雪莲语音服务');
  }
  ensureReady() {
    if (this.starting) return this.starting;
    this.starting = this.start().finally(() => { this.starting = null; });
    return this.starting;
  }
  async start() {
    if (this.stopped) throw new Error('语音插件已停用');
    try { await this.healthy(); return; }
    catch (error) {
      // Only connection refusal authorizes spawning; a busy worker must be reused.
      if (error?.code !== 'ECONNREFUSED') throw error;
    }
    if (!this.config().autoStart) throw new Error('本地语音服务尚未启动');
    const dir = configuredDirectory(this.config());
    const python = pythonPath(dir);
    const server = join(dir, 'tts_server.py');
    if (!existsSync(python) || !existsSync(server)) throw new Error('冬雪莲语音项目目录不完整');
    if (!this.child || this.child.exitCode !== null) {
      mkdirSync(this.dataDir, { recursive: true });
      const fd = openSync(join(this.dataDir, 'tts.log'), 'a');
      try {
        this.child = spawn(python, [server, '--port', '9881'], { cwd: dir, windowsHide: true,
          env: { ...process.env, PYTHONUNBUFFERED: '1', PYTHONUTF8: '1' }, stdio: ['ignore', fd, fd] });
      } finally { closeSync(fd); }
      this.child.on('error', e => this.warn(`语音进程启动失败：${e.message}`));
      this.log('正在加载本地冬雪莲 v2Pro 模型');
    }
    const child = this.child;
    for (let i = 0; i < 120; i++) {
      if (this.stopped) throw new Error('语音插件已停用');
      if (child.exitCode !== null || child.pid === undefined) throw new Error('语音服务退出，请查看插件的 tts.log');
      try { await this.healthy(); this.log('冬雪莲语音服务就绪'); return; } catch (e) {
        if (e?.code !== 'ECONNREFUSED' && !String(e?.message).includes('超时')) throw e;
      }
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
    throw new Error('语音服务启动超时，请查看插件的 tts.log');
  }
  async synthesize(text, signal) {
    await this.ensureReady();
    return localRequest('/tts', { text, timeoutMs: Math.max(5000, Math.min(120000, Number(this.config().timeoutMs) || 60000)),
      signal: AbortSignal.any([signal, this.abort.signal]) });
  }
  stop() {
    if (this.stopped) return;
    this.stopped = true; this.abort.abort();
    // Never terminate an existing service started by another launcher.
    const child = this.child;
    if (child?.pid && child.exitCode === null) {
      if (process.platform === 'win32') {
        const killer = spawn('taskkill.exe', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' });
        killer.on('error', () => {});
      } else child.kill();
    }
    this.child = null;
  }
}
