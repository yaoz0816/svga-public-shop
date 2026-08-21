import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const configFile = new URL('../vercel.json', import.meta.url);
const ignoreFile = new URL('../.vercelignore', import.meta.url);

test('standalone deployment publishes only generated output', () => {
  const config = JSON.parse(readFileSync(configFile, 'utf8'));

  assert.equal(config.outputDirectory, 'output');
  assert.equal(config.cleanUrls, true);
});

test('standalone deployment excludes collector inputs', () => {
  const ignoredPaths = readFileSync(ignoreFile, 'utf8')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  assert.deepEqual(ignoredPaths, [
    '.venv',
    'docs',
    'scripts',
    'tests',
    'svga_public_catalog/',
    'output/*.json',
  ]);
});
