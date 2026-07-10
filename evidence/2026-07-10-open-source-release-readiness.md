# Open-Source Release Readiness Receipt

Date: 2026-07-10
Status: SHIPPING
Plan row: 6.0.4

## Claim

Vidux now produces a bounded, reproducible, globally installable npm release
candidate from the tracked repository state. The release helper synchronizes
all version surfaces, the packaged CLI self-locates outside a source checkout,
and public installation docs match the behavior exercised from an isolated
consumer environment.

This is release-candidate proof, not publication proof. The GitHub repository
is still private, GitHub has no release, the npm name currently returns E404,
and no tag, registry publish, or visibility change was performed. Benchmark v2
also remains blocked on its independent fixture release, with 0 verified
net-win scenario classes.

## Red Baseline

Before this slice, `npm pack --dry-run --json` produced 6,811 files and about
30.8 MB unpacked. It included untracked `.opencode/`, `evaluations/`, and local
evidence. `package.json` was private and had neither a CLI `bin` entry nor a
shipping allowlist. `vidux release` changed `VERSION` without synchronizing
the npm lockfile or Claude plugin manifest.

## Product Changes

- `package.json` and `.npmignore` define a Node 20+, public-provenance release
  candidate with an explicit `vidux` binary and extension-level file allowlist.
- `scripts/vidux-release-package.py` builds the exact candidate twice in
  isolated directories and fails closed on byte drift, version drift, missing
  runtime files, untracked content, forbidden local/proof roots, or size/count
  ceilings.
- `scripts/vidux-release.sh` synchronizes `VERSION`, `package.json`,
  `package-lock.json`, and `.claude-plugin/plugin.json`, verifying the candidate
  before and after a release bump.
- `vidux build` now includes package verification. `vidux doctor` keeps Python,
  token permissions, stale runtime state, and config as hard failures while
  treating optional GitHub, development-root, and source-test capabilities as
  warnings in a packaged install.
- README, installation, quickstart, command, support, contribution, and script
  references now distinguish source checkout, tarball/global install, and
  external publication truth.
- Codex review found a packaged `.claude/settings.json` note naming a private
  account and command policy. The note is repository-neutral now, and the
  public-ready scanner has a narrow regression for that leak class.

## Package Proof

```text
npm run release:verify -- --json
PASS
version: 2.23.0
file_count: 186
packed_bytes: 553408
unpacked_bytes: 1823683
reproducible: true
sha256: 1ea1fa98f5537a4710025230ba963c33cc0fa9aac7e7577d7aa012a9c98b0ecb
errors: []
```

The candidate contains the CLI, browser, static assets, public docs, plugin
manifest, and runtime helpers. It excludes `.git`, `.github`, `.opencode`,
`evaluations`, `evidence`, `investigations`, `projects`, `prompts`, tests,
generated reports, package locks, local plans, JSONL data, tokens, keys, logs,
and environment files. Every packed path is git-tracked.

## Consumer Smoke

The final tarball was installed with `npm install --global --prefix <isolated>
<tarball>` under isolated `HOME`, `TMPDIR`, install prefix, and project roots:

```text
vidux --version: 2.23.0
vidux init --here: PASS
second vidux init --here: exit 1 (existing PLAN.md preserved)
vidux doctor: exit 0; 5/7 passed, 2 optional warnings
/api/health: ok=true
/api/plans: 1 plan
browser root: 5345 bytes
installed tarball sha256: 1ea1fa98f5537a4710025230ba963c33cc0fa9aac7e7577d7aa012a9c98b0ecb
```

The two warnings were expected in the isolated package: GitHub authentication
was unavailable and the source-only test tree was intentionally absent.

## Mechanical Floor

```text
bin/vidux build
PASS - docs + 11 JavaScript tests + 833 Python tests (5 skipped) + release package

python3 -m unittest tests.test_public_ready_grep_gate tests.test_release_package tests.test_release_script
PASS - 37 tests

npm run public-ready:grep
PASS - 390 tracked files

npm run test:e2e
PASS - 120/120 desktop, iPad, and iPhone journeys

npm audit --audit-level=high
PASS - 0 vulnerabilities

python compile, shell syntax, git diff --check, git diff --cached --check
PASS
```

## Remote And Mount Truth

- A fresh fetch found the branch 0 commits behind `origin/main` before this
  closeout commit. PR #8 was open, non-draft, merge-clean, and its existing
  Graphite and gitleaks checks were green.
- GitHub reports `firstbitelabsllc/vidux` as PRIVATE with no latest release.
  The npm registry reports the `vidux` package unavailable/unpublished.
- Skillbox's broad doctor reports unrelated drift in other shared skills. Vidux
  itself is consistent across all reported roots, and the active AI, Claude,
  Codex, Agents, and OpenCode mounts resolve to this checkout. Source-list
  validation passed.
- The intentionally untracked `.opencode/`, `evaluations/`, and July 7 local
  verification receipts were not staged, deleted, normalized, or packaged.

## Independent Review

- GLM independently reproduced the 186-file package, byte-identical hash,
  version synchronization, packaged CLI self-location, focused tests, and
  doctor behavior, then returned `NO BLOCKER FOUND`.
- Grok exhausted its bounded turn budget after local hook/MCP bootstrap and
  file-tool failures without a verdict. It is recorded unavailable, not green.
- Fable was not invoked because this slice required no hard architecture or
  product decision; mechanical evidence and Codex adjudication owned the call.
- Codex found and fixed the private packaged settings note, distinguished a
  dead shared temp pidfile from isolated package behavior, and reran the final
  package, doctor, browser, build, public-boundary, syntax, and diff gates.

Model opinions are not proof. No concrete unfixed blocker remains after
adjudication against the commands and artifacts above.

## Verdict

Row 6.0.4 is SHIPPING as a reproducible release candidate. The repository can
be made public and the package can be tagged/published without reworking its
shipping boundary, but those external actions remain deliberate hard rails.
Vidux's engineering readiness improved; its quantitative superiority claim did
not. Benchmark v2 remains the authority for that decision.
