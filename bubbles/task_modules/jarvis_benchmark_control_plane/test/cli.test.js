import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import test from 'node:test';
import { PROJECT_ROOT } from '../src/config.js';

test('CLI validate command exits cleanly with machine-readable proof', () => {
  const result = spawnSync(process.execPath, ['src/cli.js', 'validate'], {
    cwd: PROJECT_ROOT,
    encoding: 'utf8',
  });
  assert.equal(result.status, 0, result.stderr);
  const output = JSON.parse(result.stdout);
  assert.equal(output.valid, true);
  assert.equal(output.ledger.valid, true);
});

test('CLI rejects unknown commands with a nonzero exit', () => {
  const result = spawnSync(process.execPath, ['src/cli.js', 'not-a-command'], {
    cwd: PROJECT_ROOT,
    encoding: 'utf8',
  });
  assert.notEqual(result.status, 0);
  assert.equal(JSON.parse(result.stderr).error.code, 'INVALID_INPUT');
});
