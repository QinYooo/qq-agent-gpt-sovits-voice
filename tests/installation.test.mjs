import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { applyInstallation } from '../plugins/azuma-voice/installation.js';

test('installer path replaces stale saved settings only once per deployment', () => {
  const directory = mkdtempSync(join(tmpdir(), 'voice-install-'));
  try {
    writeFileSync(join(directory, 'tts_server.py'), '# fixture');
    const file = join(directory, 'installation.json');
    const values = new Map();
    const patches = [];
    const storage = { get: (k, d) => values.has(k) ? values.get(k) : d, set: (k, v) => values.set(k, v) };
    const args = { storage, setConfig: patch => patches.push(patch) };
    writeFileSync(file, JSON.stringify({ version: 1, generation: 'a'.repeat(32), projectDir: directory }));
    assert.equal(applyInstallation(file, args), true);
    assert.deepEqual(patches, [{ sovitsDir: directory }]);
    assert.equal(applyInstallation(file, args), false); // A later UI edit is preserved.
    writeFileSync(file, JSON.stringify({ version: 1, generation: 'b'.repeat(32), projectDir: directory }));
    assert.equal(applyInstallation(file, args), true);
    assert.equal(patches.length, 2);
    assert.equal(Object.keys(patches[0]).length, 1);
  } finally { rmSync(directory, { recursive: true, force: true }); }
});

test('missing deployment file is a manual install; invalid deployment cannot change settings', () => {
  const directory = mkdtempSync(join(tmpdir(), 'voice-invalid-'));
  try {
    const file = join(directory, 'installation.json');
    const args = { setConfig: () => assert.fail('must not write config'), storage: {} };
    assert.equal(applyInstallation(file, args), false);
    writeFileSync(file, JSON.stringify({ version: 1, generation: 'c'.repeat(32), projectDir: 'relative' }));
    assert.throws(() => applyInstallation(file, args), /安装路径/);
  } finally { rmSync(directory, { recursive: true, force: true }); }
});
