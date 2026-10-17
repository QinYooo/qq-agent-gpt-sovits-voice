import test from 'node:test';
import assert from 'node:assert/strict';
import { resolve } from 'node:path';
import { configuredDirectory, LocalWorker } from '../plugins/azuma-voice/worker.js';

test('public defaults require a user-supplied absolute project directory', () => {
  for (const sovitsDir of ['', '   ', 'relative/project']) {
    assert.throws(() => configuredDirectory({ sovitsDir }), /绝对路径/);
  }
  assert.equal(configuredDirectory({ sovitsDir: resolve('voice-project') }), resolve('voice-project'));
});

test('stopped worker cannot start or terminate an externally managed service', async () => {
  const worker = new LocalWorker({ config: () => ({ autoStart: false }), dataDir: '' });
  worker.stop();
  worker.stop();
  await assert.rejects(worker.ensureReady(), /停用/);
  assert.equal(worker.child, null);
});
