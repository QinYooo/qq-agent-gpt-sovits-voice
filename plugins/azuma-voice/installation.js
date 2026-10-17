import { existsSync, readFileSync } from 'node:fs';
import { isAbsolute, join } from 'node:path';

// Apply only the explicit local installer's path, once per deployment. Later UI
// edits remain effective; no other plugin, trust or account setting is touched.
export function applyInstallation(file, { storage, setConfig, log = () => {} }) {
  if (!existsSync(file)) return false;
  const install = JSON.parse(readFileSync(file, 'utf8'));
  if (install.version !== 1 || !/^[a-f0-9]{32}$/.test(install.generation || '')
    || typeof install.projectDir !== 'string' || !isAbsolute(install.projectDir)
    || !existsSync(join(install.projectDir, 'tts_server.py'))) {
    throw new Error('安装路径记录无效，请从完整项目所在位置重新运行插件安装脚本');
  }
  if (storage.get('installationApplied', '') === install.generation) return false;
  setConfig({ sovitsDir: install.projectDir });
  storage.set('installationApplied', install.generation);
  log('已根据本次安装位置同步语音项目路径');
  return true;
}
