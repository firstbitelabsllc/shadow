import { execFileSync } from 'node:child_process';
import { mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';

export default async function globalSetup() {
  const root = process.env.SHADOW_TEST_DEV_ROOT;
  if (!root) throw new Error('SHADOW_TEST_DEV_ROOT is required');
  const boundedRoot = resolve(root);
  const testResults = resolve('.shadow-test');
  const relation = relative(testResults, boundedRoot);
  if (!relation || relation.startsWith('..') || relation.includes('/../')) {
    throw new Error('browser fixture root must stay under .shadow-test');
  }
  rmSync(boundedRoot, { recursive: true, force: true });
  mkdirSync(join(boundedRoot, 'demo'), { recursive: true });
  writeFileSync(join(boundedRoot, 'demo', 'PLAN.md'), `# Release notes

## Operator Brief

- Outcome ID: ship-release-notes
- Outcome Revision: 7
- Outcome Updated At: 2026-08-03T02:00:00Z
- Outcome State: needs_input
- Outcome: Publish release notes people can trust.
- Next: Choose the final review depth.
- Decision ID: choose-review-depth
- Decision: How should we finish the review?
- Option A ID: ship-now
- Option A: Ship now
- Option A Consequence: Use the accepted proof and finish today.
- Option B ID: cold-review
- Option B: Run a cold review
- Option B Consequence: Spend one bounded pass on independent judgment.
- Option C ID: hold-release
- Option C: Hold the release
- Option C Consequence: Keep the Outcome open until new evidence exists.
- Proof ID: focused-tests
- Proof: tests/test_browser.py
- Proof Summary: Browser contract tests pass.
- Proof Delivery: delivered

## Work

- [in_progress] Choose the final review depth

## Progress

- 2026-08-03: The bounded implementation is ready for a decision.

<!-- shadow-drive.v1
{
  "schema": "shadow.drive.v1",
  "revision": 1,
  "lanes": [
    {
      "id": "improve-copy",
      "state": "ready",
      "task_kind": "dev",
      "summary": "Make the release note easier to understand.",
      "task": "Clarify the release note and keep the focused check green.",
      "allowed_paths": ["PLAN.md"],
      "proof": ["python3", "-m", "unittest", "tests.test_browser"],
      "merge": "manual"
    }
  ]
}
-->
`, 'utf8');
  mkdirSync(join(boundedRoot, 'gift'), { recursive: true });
  writeFileSync(join(boundedRoot, 'gift', 'PLAN.md'), `# Gift flow live

## Operator Brief

- Entity: snowcubes
- Mode: Close
- Milestone: Gift flow live on storefront
- Outcome ID: gift-flow-live
- Outcome Revision: 3
- Outcome Updated At: 2026-08-05T02:00:00Z
- Outcome State: working
- Outcome: Gifting works end to end on the storefront.
- Next: Publish the live theme with pixel proof.
- Proof ID: gift-tests
- Proof: tests are green on the preview theme.
- Proof Summary: Focused gift tests pass.
- Proof Delivery: delivered

## Checkpoints

### M1 — Gift flow live
- [completed] C1 Gift wrap option renders | proof: npm run test:pdp | size: S
- [in_progress] C2 Checkout smoke green | proof: npm run smoke | size: M
- [pending] C3 (DoD) Live publish with pixel proof | proof: npm run verify | size: S

## Progress

- 2026-08-05: checkout smoke under way.
`, 'utf8');
  execFileSync('git', ['init', '-q'], { cwd: boundedRoot });
  execFileSync('git', ['config', 'user.email', 'test@example.invalid'], { cwd: boundedRoot });
  execFileSync('git', ['config', 'user.name', 'Shadow Test'], { cwd: boundedRoot });
  execFileSync('git', ['add', 'demo/PLAN.md', 'gift/PLAN.md'], { cwd: boundedRoot });
  execFileSync('git', ['commit', '-qm', 'fixture'], { cwd: boundedRoot });
}
