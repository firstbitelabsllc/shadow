import { readdirSync, readFileSync, statSync } from 'node:fs';
import { resolve } from 'node:path';

// macOS can offload an otherwise local checkout and block for tens of seconds
// on the first file read. Hydrate the small, read-only unit-test inputs before
// per-test clocks start; tests still perform their own reads and assertions.
const INPUTS = [
  'browser/static',
  'browser/tests/e2e/global-setup.ts',
  'browser/tests/fixtures/fake-dev-root',
  'browser/tests/unit',
  'playwright.config.ts',
];

function hydrate(path) {
  for (const entry of readdirSync(path, { withFileTypes: true })) {
    const child = resolve(path, entry.name);
    if (entry.isDirectory()) hydrate(child);
    else if (entry.isFile()) readFileSync(child);
  }
}

export default function setup() {
  for (const relative of INPUTS) {
    const path = resolve(relative);
    if (statSync(path).isDirectory()) hydrate(path);
    else readFileSync(path);
  }
}
