# C75 Editor Limit Truth

Date: 2026-05-25
Surface: Moussey `/coding`

## Goal

Use the visible C74 handoff verifier failure to run the next bounded editor action, then make the admin console report the real editor outcome instead of flattening it to a generic `exit 1`.

## Run

Command:

```text
curl -N -X POST \
  -H 'Content-Type: application/json' \
  -d '{"jobId":"resplit-web-autobot","mode":"codex-editor","label":"local-ci-resplit_web_integration","handoffId":"223131fe-cc49-4b23-a923-0e56d734d610"}' \
  http://127.0.0.1:4321/api/coding/lanes/run
```

Result:

```text
runId: e7d31368-f4dc-4be0-9c37-54ca3673e421
handoffId: 223131fe-cc49-4b23-a923-0e56d734d610
mode: codex-editor
laneRunKind: codex-agent-editor
baseRef: origin/main
durationMs: 51500
exitCode: 1
teardownOk: true
patchPath: null
```

The lane created a clean `origin/main` Resplit Web worktree, installed dependencies, built Next, started `http://127.0.0.1:3110`, and entered nested Codex. Nested Codex then returned:

```text
You've hit your usage limit. Visit https://chatgpt.com/codex/settings/usage to purchase more credits or try again at 4:34 AM.
```

The route ran `git diff --check`, found no patch, stopped the server, removed the worktree, deleted the branch, and released the port lock.

## UI Fix

- `handoffResultFromRunHistory` now summarizes failed handoff runs from `stderrTail`/`stdoutTail`.
- Usage-limit failures render as `usage limit` in the first-viewport `Agent Result` / `Handoff Result` cards.
- Missing `#globe` verifier failures render as `missing #globe`.

## Verification

Moussey checks:

```text
git diff --check -- app/coding/page.tsx
npm run build
launchctl kickstart -k gui/$UID/com.leokwan.moussey-server
curl -fsS --max-time 5 http://127.0.0.1:4321/api/health
```

Result: build passed with the known local-CI artifact Turbopack NFT warning; live health returned `ok:true`.

Browser proof:

```text
url: http://127.0.0.1:4321/coding?handoff=223131fe-cc49-4b23-a923-0e56d734d610&fresh=c75-usage-limit-truth
screenshot: projects/agentic-coding-workbench/evidence/2026-05-25-c75-usage-limit-truth.png
usage limit visible: true
run e7d31368 visible: true
console errors: 0
page errors: 0
horizontal overflow: 1440/1440
```

## Verdict

C75 did not produce a Resplit Web source patch because the Codex account hit usage limits. The command center now tells that truth directly in the first viewport and preserves the cleaned-up failed run in history.

Next bounded options:

- Wait for Codex usage reset and rerun `Codex Editor` from the same handoff.
- Use a manual/disposable worktree patch lane for the stale `#globe` assertion.
- Keep local Aider/Gemma/Qwen as experimental until they produce changed source plus passing postcheck.
