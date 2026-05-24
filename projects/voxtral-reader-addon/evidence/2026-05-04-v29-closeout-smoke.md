# V29 Reader PR Closeout + Final No-Synthesis Smoke - 2026-05-04

## What Changed

- Added `test_readaloud_project_a_acceptance_contract` to lock the official reader surface:
  - status-only top bar
  - persistent footer player
  - annotation FAB
  - local Voxtral MLX loopback server contract
  - segment inventory
  - per-segment cache and merge path
  - segment timeline seek/highlight path
  - section-level read controls
  - offline launcher / auto-reprobe
  - cache clearing and quota pruning
  - fixture coverage for the player states

## Browser Smoke

Worktree preview:

```text
http://127.0.0.1:7297/?plan=codex-voxtral-mlx-reader-20260502%2Fprojects%2Fvoxtral-reader-addon%2FPLAN.md
```

Environment:

```text
VIDUX_BROWSER_PORT=7297
VIDUX_DEV_ROOT=/Users/leokwan/Development/vidux-worktrees
```

Observed with browser automation:

```json
{
  "title": "vidux browser",
  "topbar": "41 plans · 10 repos · 0 artifacts · 505/614 tasks (82%)\\n↻ refresh",
  "playerVisible": true,
  "status": "Ready",
  "sectionButtons": 80,
  "firstSectionLabel": "Read this section: Ship a 🔊 \"Read aloud\" button in vidux-browse that re...",
  "annotationFab": true
}
```

No `Read` click was made. No model weights were downloaded. No audio was synthesized.

Screenshot:

- `evidence/2026-05-04-v29-closeout-smoke.png`

## PR State

- PR: `https://github.com/leojkwan/vidux/pull/87`
- Branch: `codex/voxtral-mlx-reader-20260502`
- Draft: yes, per automation instruction
- Merge state at closeout: clean
- Checks at closeout:
  - Contract tests: pass
  - Doc structure: pass
  - Plan GC tests: pass
  - ShellCheck: pass
  - Worktree GC tests: pass
  - Graphite / AI Reviews: skipped

## Verification

```text
node --check browser/static/readaloud.js
python3 -m py_compile browser/scripts/voxtral_mlx_server.py
bash -n browser/scripts/start-voxtral-mlx-server.sh
python3 -m unittest tests.test_browser_server.BrowserReadaloudStaticContractTests
git diff --check
npm test
gh pr checks 87 --watch --interval 10
```
