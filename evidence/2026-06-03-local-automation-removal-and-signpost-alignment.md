# Local Automation Removal and Signpost/Core Alignment

Date: 2026-06-03

## Intent

Leo asked to delete local automations running on this computer without his knowledge, then align the remaining Vidux signposting and core-finalization work.

## Removed From This Mac

Stopped with `launchctl bootout`, disabled with `launchctl disable`, and deleted from `~/Library/LaunchAgents`:

- `com.leokwan.resplit-watch`
- `com.leokwan.resplit-2-0-loop`
- `com.leokwan.linear-health-watch`
- `com.leokwan.moussey-slack-listener`

Also deleted stale cron-like backup/disabled plist files so they cannot be accidentally reloaded:

- `com.leokwan.resplit-watch.plist.bak`
- `com.leokwan.resplit-2-0-loop.plist.bak`
- `com.leokwan.resplit-2-0-loop.plist.disabled-20260526220855`
- `com.leokwan.linear-health-watch.plist.bak`
- `com.leokwan.autobot-resplit-web.plist.disabled-20260526220855`
- `com.leokwan.lead-cron.plist.disabled-20260526220855`
- `com.leokwan.grafana-observability.plist.disabled`
- `com.leokwan.deploy-watcher.plist.bak`

## Verification

- `launchctl list | rg 'com\.leokwan\.(resplit-watch|resplit-2-0-loop|linear-health-watch|moussey-slack-listener|autobot-resplit-web|lead-cron|deploy-watcher|grafana-observability)'` returned no matches.
- `zsh -f -c 'setopt null_glob; ... ~/Library/LaunchAgents/com.leokwan.<target>*'` returned no matching target plist files.
- `crontab -l` returned `crontab: no crontab for leokwan`.
- `launchctl print-disabled gui/$(id -u)` now shows the targeted labels as disabled: `resplit-watch`, `resplit-2-0-loop`, `linear-health-watch`, `moussey-slack-listener`, `autobot-resplit-web`, `lead-cron`, `deploy-watcher`, and `grafana-observability`.
- `pmset -g sched` shows only an Apple invisible wake alarm: `com.apple.alarm.user-invisible-com.apple.acmd.alarm`.

Remaining Leo-owned launchd files after cleanup:

- `com.leokwan.codex-lb.plist`
- `com.leokwan.mlx-audio.plist`
- `com.leokwan.moussey-kokoro-tts.plist`
- `com.leokwan.moussey-mlx-lm.plist`
- `com.leokwan.moussey-parakeet-stt.plist`
- `com.leokwan.moussey-server.plist`
- `com.leokwan.moussey-server.plist.bak-20260530T035247Z`
- `com.leokwan.vidux-browser.plist`
- `com.leokwan.vidux-voxtral-mlx.plist`

These were left in place because they are local services or backups, not scheduled recurring automation rows. In particular, `com.leokwan.vidux-browser` keeps the current Vidux browser surface available for real UI proof.

## Alignment

Local scheduled automation on this Mac is now opt-in only. Any future LaunchAgent or cron-style agent should have:

- an explicit owning plan row and user-visible purpose;
- an install/remove command recorded in evidence;
- `VIDUX_AUTOMATION_NAME` or `CLAUDE_AUTOMATION_NAME` attribution;
- `VIDUX_SIGNPOST_RUN_ID` coverage for the run or cycle;
- a visible stop/disable path in the handoff;
- no Slack, Linear, GitHub, PR, deployment, or human-message mutation without explicit approval.

Vidux signposting support already exists for local proof:

- `vidux signpost emit|summary|trace|wrap`;
- `vidux signpost lifecycle-smoke --json`;
- `vidux signpost spawned-subagent-smoke --json`;
- runtime/thread/automation attribution fields in `scripts/vidux_signpost.py`;
- signpost regression coverage in `tests/test_signpost.py`;
- README and command-reference docs for the local smoke/non-claim boundary.

Remaining signposting/core finalization work:

- keep root `5.3.1` parked unless the Resplit `gh pr create` overlap is solved or the row is explicitly replanned away from local scheduled automation;
- add any future local automation only behind the opt-in/signposted/visible policy above;
- decide whether a hook installer/runner belongs in core, because current proof is local smoke and does not claim real external Codex/Claude/Cursor launches;
- keep browser UI work on `projects/vidux-browser/PLAN.md` at `VB-COM-8` for anchor markers and target map;
- keep cleanup/destructive work behind explicit owner approval.

Next resume point: use this file plus `PLAN.md`, `projects/team-agent-coordination/PLAN.md`, and `projects/vidux-browser/PLAN.md`. Do not reinstall the removed local automations while trying to satisfy older phase-shift LaunchAgent proof rows.
