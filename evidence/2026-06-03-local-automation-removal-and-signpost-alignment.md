# Local Automation Removal and Signpost/Core Alignment

Date: 2026-06-03

## Intent

The maintainer asked to delete local automations running on this computer without their knowledge, then align the remaining Vidux signposting and core-finalization work.

## Removed From This Mac

Stopped with `launchctl bootout`, disabled with `launchctl disable`, and deleted from `~/Library/LaunchAgents`: 4 LaunchAgents unrelated to Vidux (other private-repo watch/loop/health-check/chat-listener jobs the maintainer had running without realizing it), plus their stale backup/disabled plist copies so none could be accidentally reloaded.

## Verification

- `launchctl list | rg 'com\.<operator>\.(...)'` (naming the 4 removed labels) returned no matches.
- `zsh -f -c 'setopt null_glob; ... ~/Library/LaunchAgents/com.<operator>.<target>*'` returned no matching target plist files.
- `crontab -l` returned `crontab: no crontab for <operator>`.
- `launchctl print-disabled gui/$(id -u)` now shows the 4 targeted labels as disabled.
- `pmset -g sched` shows only an Apple invisible wake alarm: `com.apple.alarm.user-invisible-com.apple.acmd.alarm`.

Remaining launchd files after cleanup (kept because they are local services or backups, not scheduled recurring automation rows): a handful of other private-repo local services, plus Vidux's own `com.<operator>.vidux-browser` and `com.<operator>.vidux-voxtral-mlx`. `vidux-browser` keeps the current Vidux browser surface available for real UI proof.

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

- keep root `5.3.1` parked unless the other-repo `gh pr create` overlap it depends on is solved, or the row is explicitly replanned away from local scheduled automation;
- add any future local automation only behind the opt-in/signposted/visible policy above;
- decide whether a hook installer/runner belongs in core, because current proof is local smoke and does not claim real external Codex/Claude/Cursor launches;
- keep browser UI work on `projects/vidux-browser/PLAN.md` at `VB-COM-8` for anchor markers and target map;
- keep cleanup/destructive work behind explicit owner approval.

Next resume point: use this file plus `PLAN.md`, `projects/team-agent-coordination/PLAN.md`, and `projects/vidux-browser/PLAN.md`. Do not reinstall the removed local automations while trying to satisfy older phase-shift LaunchAgent proof rows.
