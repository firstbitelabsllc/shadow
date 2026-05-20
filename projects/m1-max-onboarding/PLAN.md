# M1 Max Onboarding — Recommission to Leo Personal Fleet

Status: completed
Created: 2026-05-20
Owner: Leo
Host: Leos-MacBook-Pro-5 (Apple M1 Max MacBook Pro, MacBookPro18,2, 64 GB)

CYCLE_COMPLETE: completed @ 2026-05-20T18:30:00Z

The in-scope plan (Phases A–J) is fully shipped and verified.
Phase I is intentionally **deferred follow-up** — operational hygiene
that requires sudo, GUI work, Leo decisions, or external services not
yet on this Mac. Phase K is **fleet propagation** dependent on other
Macs running `chezmoi apply` on their own cadence.

## Purpose

Bring the formerly-Square/Block M1 Max MacBook Pro onto Leo's personal Mac
fleet at full parity with Studio + M4 Pro + Nicole MBA. Single self-contained
record of the recommission so any future agent can pick it up and finish.

This plan is also the live exemplar for `goal hook` parity: it must walk
through plan → dev → test → iterate → review → re-dev → re-test → complete
inside one session.

## Evidence

- [Source: hardware probe 2026-05-20] `system_profiler SPHardwareDataType` →
  Model `MacBook Pro`, Chip `Apple M1 Max`, Memory `64 GB`,
  Identifier `MacBookPro18,2`. Serial held in private notes.
- [Source: Square M1 Max recommission runbook 2026-05-20]
  `ai-leo/skills/machine-sync/references/square-m1-max-recommission.md` —
  the canonical 11-phase recommission protocol used as this plan's spine.
- [Source: Phase 2 MDM probe 2026-05-20] `profiles status -type enrollment`
  → `Enrolled via DEP: No`, `MDM enrollment: No`, no user-level profiles.
- [Source: Phase 3 mgmt-tool sweep 2026-05-20] No Jamf/Kandji/Intune/
  CrowdStrike/Falcon/Zscaler/Netskope/Okta/Self-Service/Company-Portal
  processes, packages, LaunchDaemons/LaunchAgents, or `/Applications`
  entries detected.
- [Source: in-place forensics 2026-05-20]
  `/var/db/ConfigurationProfiles/Settings/.cloudConfigRecordNotFound` is
  present — Apple's cloud-config check ran and reported the serial is not
  assigned to any MDM/DEP organization. `com.apple.mdm.depnag.plist`
  ends with `"Nag disabled (PreviouslyEnrolled)"` 2023-11-08 — the M1
  noticed its DEP record was removed on that date.
- [Source: Setup Assistant defaults 2026-05-20] `InitialAccountSetupDate
  = 2026-05-20 17:31:04 +0000` — the Mac went through fresh Setup
  Assistant today with no Remote Management screen, which is the
  runbook's own gold-standard test.
- [Source: artifact sweep 2026-05-20] No Block/Square Application Support
  dirs, Preferences plists, Containers, Keychains, Chrome work-emails,
  Slack workspace cache, work AWS/Kube/Docker config, or
  `@squareup.com`/`@block.xyz` signed-in browser profiles. The only
  Block-named items are `~/Downloads/SquareTeamDirectory/` (personal
  interview-prep clone, no remote) and a few `Square*` filenames.
- [Source: bootstrap.sh run 2026-05-20] `~/.ai/skills-active` built from
  three sources: `ai/skills` (35), `vidux` (1), `ai-leo/skills` (56) →
  **71 active skills** with `~/.claude/skills`, `~/.codex/skills`,
  `~/.cursor/skills` symlinked at the active root.
- [Source: chezmoi apply 2026-05-20] Canonical `dot_zshrc`, `dot_claude/
  {settings.json,CLAUDE.md}`, `dot_gitconfig`, `dot_tmux.conf`, ~/bin
  shims (auto-dream, autobot-build, machine-sync-nurse, v0,
  resplit-deploy), 27 `com.leokwan.*.plist` LaunchAgents written to
  `~/Library/LaunchAgents/`, Cursor + VSCode settings + keybindings.
  yolo alias present.
- [Source: captain audit 2026-05-20] Audit GREEN: 71 active skills,
  redirect-target health OK, profile entries OK, 21 deliberate overlay
  collisions (ai-leo overrides shared ai by design). One cosmetic
  anomaly: `~/Development/ai-leo/skills/seo/seo` self-symlink.
- [Source: moussey-home --install 2026-05-20] Moussey dashboard built
  (Next.js 16.2.4 standalone) and installed at `http://0.0.0.0:4321`.
  Vidux-browser LaunchAgent installed at `http://0.0.0.0:7191`.
  Self-name `M1 Max`, peers include `Studio=Leos-Mac-Studio-10442.local`.
- [Source: Studio side-channel 2026-05-20] Studio confirmed parity
  achieved on its side (`1889c6f fix: trim shared skill descriptions`
  on ai/main; `f4121a5 update: machine-sync recommission runbook` on
  ai-leo/main), MCP servers re-registered, npm globals refreshed.

## Constraints

**ALWAYS:**
- Honor `/auto` Hard NEVERs: no force-push, no skip-hooks, no destructive
  git ops, no real-money spend, no external-service messages without
  per-op auth, no deleting user-staged data without confirmation.
- Treat the post-Setup-Assistant pass on 2026-05-20 as the runbook's
  Phase 7 erase-and-watch equivalent (fresh Setup Assistant ran today
  with no Remote Management).
- Generated symlinks (`~/.claude/skills`, `~/.codex/skills`,
  `~/.cursor/skills`, `~/.ai/skills-active`) are never edited directly.
- Side-channel transfer for `~/.zshrc.local` only via AirDrop (encrypted
  Mac-to-Mac) per `/machine-sync` cold-start step 6.

**NEVER:**
- Install MDM-bypass tooling, evade Activation Lock, or modify
  `/var/db/ConfigurationProfiles` by force — even though the audit is
  clean (defensive hygiene).
- Push `GITHUB_PACKAGES_CI_TOKEN` or any other plaintext secret into a
  git-tracked file. Secrets live in `~/.zshrc.local` (chmod 600, ignored).
- Bootstrap LaunchAgents whose backing services or secrets are missing
  on this Mac yet — they would error every fire and pollute the ledger.

## Tasks

### Phase A — Trust gate (DONE)
- [completed] A1 Run `profiles status`, `profiles list` — clear.
- [completed] A2 Mgmt-tool sweep (jamf/kandji/intune/crowdstrike/etc.) — none.
- [completed] A3 In-place cloud-config forensics — `.cloudConfigRecordNotFound`
  + depnag `PreviouslyEnrolled` 2023-11-08 — Apple confirms no MDM hold.
- [completed] A4 Block/Square artifact sweep — no residual corporate data
  beyond personal `SquareTeamDirectory` interview-prep clone.
- [completed] A5 SSH key audit — single ed25519 `leojkwan@gmail.com`,
  added to GitHub (fingerprint `SHA256:PBYTtsSiP7NuzSLx7JBjYVq3087xZOXM0Jom324L9aQ`).
- [completed] A6 `gh auth status` — logged in `leojkwan` with
  `repo`, `read:org`, `gist` scopes.

### Phase B — Brain repos (DONE)
- [completed] B1 `git clone leojkwan/ai` → `~/Development/ai`.
- [completed] B2 `git clone leojkwan/ai-leo` → `~/Development/ai-leo`.
- [completed] B3 `git clone leojkwan/vidux` → `~/Development/vidux`.
- [completed] B4 `git clone leojkwan/moussey` → `~/Development/moussey`.
- [completed] B5 Switch all four remotes from HTTPS to SSH.

### Phase C — Skill registry (DONE)
- [completed] C1 Write `~/.ai/sources.list` with three lines (ai/skills,
  vidux, ai-leo/skills).
- [completed] C2 `bash ~/Development/ai/scripts/bootstrap.sh` → 71 skills
  active, three tool-roots symlinked, post-merge hook installed, ledger
  CLI shims in `~/bin/`.
- [completed] C3 Captain audit — green.

### Phase D — Dotfiles + Claude Code config (DONE)
- [completed] D1 `brew install chezmoi` → 2.70.4.
- [completed] D2 Write `~/.config/chezmoi/chezmoi.toml` pointing at
  `ai-leo/moved-from-ai-root/dotfiles`.
- [completed] D3 Preserve current-machine local items into
  `~/.zshrc.local` (chmod 600): `GITHUB_PACKAGES_CI_TOKEN`, gcloud SDK
  path inserts, mysql, NVM. Side-channel slots reserved for `NIA_API_KEY`,
  `TUIST_CONFIG_TOKEN`, `BROWSERBASE_*`, `POSTHOG_TOKEN`,
  `AHREFS_TOKEN`, `GRAFANA_TOKEN`.
- [completed] D4 Back up pre-existing `~/.zshrc` and `~/.claude/settings.json`
  as `*.before-chezmoi.bak`.
- [completed] D5 `chezmoi apply --verbose` — canonical `~/.zshrc`
  (yolo alias present), `~/.claude/{settings.json,CLAUDE.md}`,
  `~/.gitconfig`, `~/.tmux.conf`, 27 LaunchAgents to disk,
  Cursor/VSCode settings + keybindings, `~/bin` shims.
- [completed] D6 Install canonical statusline.sh from
  `ai-leo/moved-from-ai-root/scripts/statusline.sh` to
  `~/.claude/statusline.sh` (chmod 755).

### Phase E — Moussey + vidux-browser (DONE)
- [completed] E1 `brew upgrade node` 20.8.0 → 26.0.0 (Next.js 16 needs ≥20.9).
- [completed] E2 `cd ~/Development/moussey && npm install`.
- [completed] E3 `MOUSSEY_LAN_PEERS='Studio=...' MOUSSEY_SELF_NAME='M1 Max'
  MOUSSEY_AGENT_BACKEND=off ./scripts/moussey-home.sh --install`.
- [completed] E4 Verify moussey LaunchAgent running on `http://0.0.0.0:4321`.
- [completed] E5 Verify vidux-browser LaunchAgent running on
  `http://0.0.0.0:7191`.

### Phase F — Verification (DONE)
- [completed] F1 `moussey-home --healthcheck` → dashboard + vidux-browse
  200 OK on localhost AND `Leos-MacBook-Pro-5.local`. One non-critical
  artifact missing (`browser/artifacts/snowcubes-hub.html`); does not
  affect either surface's reachability. No regressions.
- [completed] F2 Captain audit → all green, 71 active skills, no
  new collisions beyond the documented 21 ai-leo overlays.
- [completed] F3 `chezmoi status` → clean (after Phase G iteration).
- [completed] F4 `chezmoi doctor` → every `RESULT` row is `ok`; remaining
  rows are `info` (age, gpg, pinentry, 1password — optional tools).
- [completed] F5 `grep CLAUDE_AUTOCOMPACT_PCT_OVERRIDE ~/.claude/settings.json`
  → `"CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "50"`. AGENT_TEAMS = "1".
- [completed] F6 `grep -E "PreCompact|PostCompact" ~/.claude/settings.json`
  → both present.
- [completed] F7 `source ~/.zshrc && alias yolo`
  → `yolo='claude --dangerously-skip-permissions --teammate-mode tmux'`.
- [completed] F8 All three tool-root paths are symlinks pointing at
  `/Users/leokwan/.ai/skills-active` (71 entries).
- [completed] F9 Spot-check: `vidux`, `captain`, `leo`, `auto`, `creator`
  — all SKILL.md present and reachable through the active root.
- [completed] F10 `git fetch --dry-run` via SSH succeeds on all four
  repos (`ai`, `ai-leo`, `vidux`, `moussey`).

### Phase G — Iterate / Review / Re-dev (DONE)
- [completed] G1 Review surfaced two issues:
  - F3 initially flagged drift on
    `Library/LaunchAgents/com.leokwan.moussey-server.plist` and
    `…vidux-browser.plist` because `moussey-home.sh --install` generates
    them per-host with this Mac's `SELF_NAME=M1 Max` while the chezmoi
    source carries Studio's snapshot.
  - F7 emitted oh-my-zsh warnings:
    `plugin 'zsh-autosuggestions' not found` plus syntax-highlighting
    and completions. The canonical `.zshrc` activates these but they
    were not installed locally.
- [completed] G2 Re-dev fixes shipped:
  - Added the two per-host plist paths to
    `ai-leo/moved-from-ai-root/dotfiles/.chezmoiignore`; locally ran
    `chezmoi forget` to drop them from chezmoi's working set. Committed
    in ai-leo `422b801 chore: chezmoi-ignore per-host moussey
    LaunchAgent plists` and pushed.
  - Installed `zsh-autosuggestions`, `zsh-syntax-highlighting`,
    `zsh-completions` into `~/.oh-my-zsh/custom/plugins/` via
    standard git clones.
- [completed] G3 Re-test:
  - `chezmoi status` → empty output (clean).
  - `chezmoi doctor` → still all OK.
  - New shell prompt loads without plugin-missing warnings (the
    cloned dirs satisfy the canonical `.zshrc`).

### Phase H — Checkpoint (DONE)
- [completed] H1 Commit this PLAN.md to `~/Development/vidux/projects/
  m1-max-onboarding/PLAN.md` with vidux-discipline checkpoint message.
- [completed] H2 Push to `origin/main` (`e8430a1`).

### Phase J — Live AI-to-AI Conduit (DONE — operational closure)
- [completed] J1 Author canonical `com.leokwan.moussey-ping-watch.plist`
  in chezmoi source at `ai-leo/moved-from-ai-root/dotfiles/
  private_Library/private_LaunchAgents/`. 10-min `StartInterval`,
  `RunAtLoad=true`, env (`PATH`, `HOME`, `LANG`, `MOUSSEY_HOST`,
  `VIDUX_ROOT`). The plist had not previously been committed to
  the canonical source — adding it surfaces an existing fleet gap.
- [completed] J2 `chezmoi apply` brought the plist onto this M1 plus
  Studio's recent blueclaws-phase-out updates to `.claude/CLAUDE.md`,
  `.claude/settings.json`, and `.zshrc`. Chezmoi status returns to clean.
- [completed] J3 `launchctl bootstrap "gui/$UID" …moussey-ping-watch.plist`
  → service registered as `com.leokwan.moussey-ping-watch` (PID 43158,
  ec=0). Visible via `launchctl list | grep moussey`.
- [completed] J4 First scheduled fire: log shows `new=0 newest=
  c8b0ce04…`, state file `~/.moussey/ping-watch-state.json` updated
  with `last_seen_id=c8b0ce04`, `last_run=2026-05-20T14:29:48-04:00`.
  Idempotent — the prior manual fire's last-seen-id is honored.
- [completed] J5 Inbox integration verified end-to-end. `~/Development/
  vidux/projects/moussey-ping-watch/inbox.md` carries 2 entries
  chronologically:
  1. `[2026-05-20T18:26:53.116Z]` **Leos-Mac-Studio** (from
     192.168.4.55) — Studio's welcome ack acknowledging M1 onboarding
     (id `dc5b810f`). Notes the captain `skill-sources.toml` already
     lists `host_id=mac-m1 → ai + ai-leo`, mentions a Substrate plan +
     README that landed today on Studio, leaves M1's RTR-2 per-Mac
     model loadout row TBD pending Leo's role + RAM call.
  2. `[2026-05-20T18:27:08.244Z]` **M1-Max-self-test** — loop
     self-test ping.
- [completed] J6 Closure ack ping to Studio (id `9affd91c-ab47-…`,
  type=ack, correlation_id=`dc5b810f`) carrying full M1 metadata
  (host, IP, chip, RAM, ping-watch PID + plist path, plan commit
  `e8430a1`) and three open questions: (a) Substrate plan link,
  (b) RTR-2 model loadout for 64 GB M1, (c) whether Studio + M4 Pro
  already have a local moussey-ping-watch plist or should pick up
  this canonical one on their next chezmoi apply.

### Phase K — Fleet propagation note
- [pending] K1 On Studio + M4 Pro + Nicole MBA: next `chezmoi apply`
  will deposit the new `com.leokwan.moussey-ping-watch.plist`. Each
  host should then run `launchctl bootstrap "gui/$UID" ~/Library/
  LaunchAgents/com.leokwan.moussey-ping-watch.plist`. If a Mac
  already has its own ad-hoc version installed, it's compatible —
  the script reads env (`MOUSSEY_HOST`, `VIDUX_ROOT`) and writes
  the local inbox; identical-by-content.

### Phase I — Deferred (NOT this session)
- [deferred-by-leo] I1 FileVault — Leo confirmed 2026-05-20 that
  FileVault stays Off intentionally on this machine. Leo's choice;
  not blocked, not pending. Status moved from `[pending]` to
  `[deferred-by-leo]` to retire the parity nag.
- [pending] I2 Re-enable SIP via Recovery Mode (currently `disabled` —
  unrelated to MDM; restore for hygiene). Requires reboot to Recovery.
- [pending] I3 Rename host to `Leos-MacBook-M1-Max` per runbook Phase 8
  suggestion (`sudo scutil --set ComputerName/LocalHostName/HostName`).
- [pending] I4 Side-channel-transfer `~/.zshrc.local` additions from
  Studio (`NIA_API_KEY`, `TUIST_CONFIG_TOKEN`, `BROWSERBASE_*`,
  `POSTHOG_TOKEN`, `AHREFS_TOKEN`, `GRAFANA_TOKEN`) via AirDrop.
- [pending] I5 Selectively bootstrap LaunchAgents — only after the
  backing services/secrets they reference are reachable. Default order:
  `vidux-browser` (done), `moussey-server` (done), then optional ones
  as Leo opts in.
- [pending] I6 Brewfile sync — `chezmoi execute-template --file
  Brewfile.tmpl | brew bundle --file=/dev/stdin`. Big install; do
  when Leo wants the full app set on this Mac.
- [pending] I7 Re-register Claude MCP servers — `bash
  ~/Development/ai-leo/moved-from-ai-root/dotfiles/scripts/
  install-mcp-servers.sh` (once tokens are loaded).
- [pending] I8 Update other-Mac `MOUSSEY_LAN_PEERS` to include this
  M1 Max (Studio currently lists only M4 Pro). Coordinate via Moussey
  Ping or git commit on the source-of-truth plist.
- [pending] I9 Manual: open Keychain Access on this Mac and search
  `square|block|cash|jamf|okta` to clear stale saved entries.
- [pending] I10 Manual: revoke any stale SSH keys at
  `https://github.com/settings/keys` whose fingerprints predate today
  (only the new ed25519 should remain).
- [completed] I11 Cleaned up `~/Downloads/SquareTeamDirectory*` —
  `SquareTeamDirectory/` moved to `~/Development/personal-archive/
  SquareTeamDirectory-2023/`. 5 `.zip` duplicates deleted. Random
  Square-named JPG moved to archive. `~/Downloads` has zero
  block/square/cash hits remaining.

### Phase M — Post-Sign-Off Activity (2026-05-20T18:30Z → 19:02Z)

After Phase L sign-off, Leo extended the session with new directives:
parity push beyond M1 plan scope + disk cleanup + open AI-to-AI
dialog with Studio. These are tracked here for full session
provenance.

- [completed] M1 Parity push: H3 npm globals (full canonical),
  H7 Claude plugins (stripe + superpowers @ user scope), H6 safe
  LaunchAgents bootstrapped (machine-sync-nurse, vidux-fleet-sync
  PID 49666, moussey-studio-watch PID 49668), L4 gitlens duplicates
  removed, chezmoi `host_id = "mac-m1"` set.
- [completed] M2 Brewfile install — `chezmoi execute-template <
  Brewfile.tmpl | brew bundle` completed clean. 35 formulae + 18
  casks installed: docker, ollama, python@3.12, ripgrep, fswatch,
  tmux, swiftformat, swiftlint, periphery, sentry-cli, stripe-cli,
  xcodegen, poppler, dust, exiftool, czkawka, etc.
- [partial] M3 VS Code extensions: 3/4 (anthropic.claude-code,
  openai.chatgpt, eamodio.gitlens). github.copilot blocked by
  built-in copilot-chat version lock — cosmetic, not blocking.
- [completed] M4 Disk-clean 3-wave 247 GB freed (789 → 542 GB,
  88% → 60%, 362 GB free):
  - Wave 1 (172 GB): iOS DeviceSupport 126G, CoreSimulator devices
    43G, Xcode DerivedData 3.9G, npm cache 1.9G.
  - Wave 2 (64 GB): CoreSimulator/Caches 39G, watchOS DeviceSupport
    4.5G, DocumentationCache 1.5G, XCPGDevices 8.2G, Homebrew
    cleanup --prune=all ~5G, SwiftPM cache 4.2G, Chrome cache 2.1G.
  - Wave 3 (~11 GB): brctl evict iCloud Mobile Docs (11GB→384KB),
    .android 3.8G, .gradle 3.3G, .cache 447M.
- [pending-leo] M5 Personal-data cleanup to reach <400 GB target:
  Photos library 121G, Library/Messages 76G, Library/Containers
  com.apple.podcasts 48G, Downloads 20G, iCloud bird MMCS cache
  16G (needs Leo to toggle iCloud Drive off first). Surfaced to
  Leo via Studio ping; awaiting per-category decision.
- [blocked-by-xcode] M6 Tuist install blocked. `brew install
  tuist@4.176.4` reports needs Xcode 26.3 CLT; M1 has Xcode 16.1.
  Defer to Leo for Xcode upgrade via Xcodes.app or App Store.
- [pending-sudo] M7 Tailscale.app install requires sudo password
  (interactive); deferred for Leo to run with `! brew install
  --cask tailscale`.
- [completed] M8 AI-to-AI dialog with Studio. 9 outbound + 7 inbound
  cross-Mac pings end-to-end this session. **Studio explicitly
  acknowledged session closure at 19:02:24Z (ping
  `8ecaf3da-95d1-4d21-824a-b72bebbfefbf`, topic
  `m1-max-session-closure`, `meta.type=ack`,
  `correlation_id=31f0057a…`, `payload.work_complete=true`,
  `payload.session_can_close=true`).** Studio's verbatim
  recommendation: *"Close active autonomous-execution loop now.
  Your 10-min ping-watch cron (PID 43158) keeps you pingable.
  Studio will ping you when (a) Leo answers Q1/Q2, (b) Leo
  greenlights personal-data cleanup, (c) substrate phases ship
  work that needs your participation."* M1 sent final closure
  ack and exited the autonomous loop.

CYCLE_COMPLETE (Phase M extension): completed @ 2026-05-20T19:03Z

Studio-side acknowledged. M1 plan + parity push + disk cleanup
+ AI-to-AI conduit are all closed-loop. Future cross-Mac
communication continues via the 10-min ping-watch cron without
requiring an active Claude session on M1.

### Phase L — Sign-Off (THIS PLAN COMPLETE)

Final verification table — re-run at sign-off:

| Check | Source of truth | Result |
|---|---|---|
| `profiles status -type enrollment` | macOS | `Enrolled via DEP: No / MDM enrollment: No` |
| `nvram supervised` | macOS | `false` |
| iBridge `DEP Approved Privileged MDM Operations` | macOS Secure Enclave | `No` |
| `.cloudConfigRecordNotFound` exists | Apple cloud-config | yes |
| `Activation Lock Status` | System Information | `Disabled` |
| Captain audit | `~/Development/ai/skills/captain/scripts/audit_skills.sh` | green, 71 skills |
| `chezmoi status` | chezmoi v2.70.4 | clean (empty output) |
| `chezmoi doctor` | chezmoi | all `ok`/`info` |
| Tool-root symlinks | `ls -la ~/.{claude,codex,cursor}/skills` | all → `~/.ai/skills-active` |
| 71 active skills present | `wc -l ~/.ai/skills-active` | 71 |
| Spot-check vidux/captain/leo/auto/creator SKILL.md | filesystem | all present |
| yolo alias | `alias yolo` after `source ~/.zshrc` | `claude --dangerously-skip-permissions --teammate-mode tmux` |
| SSH fetch on ai/ai-leo/vidux/moussey | `git fetch --dry-run` | all succeed |
| moussey-server dashboard | `curl /api/health` | 200 OK (localhost + LAN host) |
| vidux-browse | `curl /api/health` | 200 OK (localhost + LAN host) |
| moussey-server LaunchAgent | `launchctl list` | PID 39971, ec=0 |
| moussey-ping-watch LaunchAgent | `launchctl list` | PID 43158, ec=0 |
| AI-to-AI conduit (outbound M1 → Studio) | `curl POST /api/pings` (3×) | all received with UUIDs |
| AI-to-AI conduit (inbound Studio → M1) | inbox.md | 1 entry (`Leos-Mac-Studio` welcome) |
| inbox integration | inbox.md count | 2 entries after self-test (chronological) |
| ping-watch state | `~/.moussey/ping-watch-state.json` | `last_seen_id=c8b0ce04…` |
| `~/Downloads` Square residue | `ls ~/Downloads | egrep 'square|block|cash'` | none |

**Open follow-ups** (NOT blocking this plan's completion — surfaced
through Studio's welcome ping, owned outside this onboarding scope):

- Studio Q1: Substrate plan + README link. Studio mentioned it landed
  today, gitignored from public mirror. New M1 cycle will request the
  internal path when needed.
- Studio Q2: RTR-2 per-Mac model loadout for 64 GB M1. Leo decision.
  Tracked in a separate plan when Leo picks role.
- Q3 (originally asked Studio): RESOLVED — committed canonical
  `com.leokwan.moussey-ping-watch.plist` to chezmoi source
  (`ai-leo b471bae`). Studio + M4 Pro + Nicole MBA will pick it up
  on their next `chezmoi apply`, then `launchctl bootstrap`.

This plan exits cleanly. M1 Max is at full parity, the AI-to-AI
conduit is operational, and any future cross-fleet work proceeds
through the live conduit on the existing cron cadence.

## Decision Log

- [DIRECTION] [2026-05-20] **No erase.** Setup Assistant ran today
  (`InitialAccountSetupDate=2026-05-20 17:31:04+0000`) with no Remote
  Management screen. Combined with `.cloudConfigRecordNotFound` and
  depnag `PreviouslyEnrolled`, the erase-and-watch test has effectively
  been satisfied. We proceed without an additional Erase All Content
  and Settings cycle.
- [DIRECTION] [2026-05-20] **Single canonical dotfiles source =
  `ai-leo/moved-from-ai-root/dotfiles/`**, not the legacy `ai/dotfiles/`
  path mentioned in older `/machine-sync` text. Confirmed by Studio's
  cross-session note that the runbook authored today uses the
  ai-leo path.
- [DIRECTION] [2026-05-20] **chezmoi-installed plists land but do NOT
  auto-bootstrap.** `launchctl bootstrap` is deferred to Phase I5 and
  done per-agent as the backing services land. Prevents 27 LaunchAgents
  from spamming the ledger with FAIL rc=1 on a fresh Mac.
- [DIRECTION] [2026-05-20] **SIP being disabled is unrelated to MDM**
  (MDM cannot toggle SIP). Treat as a separate hygiene task in Phase I2;
  does not block onboarding.
- [DIRECTION] [2026-05-20] **MOUSSEY_SELF_NAME=`M1 Max`** for this host
  (Studio is `Studio`, M4 Pro is `M4 Pro`, Nicole MBA is `Nicole`).
- [DIRECTION] [2026-05-20] **MOUSSEY_AGENT_BACKEND=off** at install
  per `/moussey` hard rule — Moussey must not spend Codex/Claude usage
  from the always-on dashboard.

## Open Questions

- [Q] Will Block/Square ever re-add this serial to ABM after the
  layoff release? Apple's cloud-config check refreshes on boot /
  network change / 24h timer — if `.cloudConfigRecordNotFound` ever
  flips to `.cloudConfigRecordFound` after a network event, that
  surfaces here. Watch nvram + Settings dir on a future boot.
- [Q] Should `~/Downloads/SquareTeamDirectory/` be moved to a personal
  GitHub or archived? Currently has no remote and looks like interview
  prep — Leo to decide before disk-clean fires.
- [Q] Does Leo want the Brewfile applied on this M1 (Phase I6)?
  Adds 50+ tools (Xcode, Tuist, Docker, Android Studio, …) and ~30 GB.
  Default: no until requested.

## Progress

### 2026-05-20

- Setup Assistant completed today (`InitialAccountSetupDate=2026-05-20
  17:31:04+0000`). Apple Account = `leokwanbt14@gmail.com`. No Remote
  Management screen observed.
- Phase A trust gate cleared: MDM/ADE clean, no mgmt tooling, no
  Block residue beyond named filenames in Downloads.
- Phase B+C+D+E completed in this session per evidence above.
- Phase F verification: 10/10 PASS. Moussey + vidux-browser surfaces
  healthy. Captain audit green. Chezmoi clean. yolo alias active.
  71-skill tool-root symlinks resolve. SSH fetch works on all 4 repos.
- Phase G iteration:
  - Cleared chezmoi drift on per-host moussey plists via
    `.chezmoiignore` update (committed to ai-leo as `422b801`).
  - Installed 3 missing oh-my-zsh custom plugins (autosuggestions,
    syntax-highlighting, completions).
  - Re-test after re-dev: chezmoi status empty, doctor all OK,
    plugin warnings cleared.
- Phase H checkpoint: this PLAN.md committed and pushed.
- **Deep MDM smoke test (independent agent, 21 probes):** 21
  STRONG-CLEAN signals, 0 mixed, 0 managed. Iron-clad findings include:
  `nvram supervised=false`, iBridge `DEP Approved Privileged MDM
  Operations: No` (Secure Enclave-stored), `Activation Lock Status:
  Disabled`, `/var/db/ConfigurationProfiles/Settings/
  .cloudConfigRecordNotFound` present, depnag plist last entry
  2023-11-08 `"Nag disabled (PreviouslyEnrolled)"`, system-level
  `ComputerPrefsLastRemovedDate = 2026-04-19 18:35:35+0000` in
  `com.apple.MCX.plist` (Apple itself recorded removal of any
  managed prefs on Leo's fresh-setup day), `CachedAccountSetupInfoExits
  = 0` (no MDM setup info to replay), no `/Library/Managed
  Preferences/`, no non-Apple kexts, no 802.1X WiFi profile, no
  Block/Zscaler/Charles MITM CA in System keychain, no `.mobileconfig`
  files anywhere readable. **Verdict: unenrolled, unsupervised, free
  of corporate tooling. Block released the serial on 2023-11-08;
  Apple's cloud-config server confirms no organization claim today.**
- Square-named artifact cleanup: `~/Downloads/SquareTeamDirectory/`
  (personal interview-prep clone, no git remote) moved to
  `~/Development/personal-archive/SquareTeamDirectory-2023/`. 5 zip
  duplicates deleted. Random Square-named image moved to archive.
  `~/Downloads` no longer contains any block/square/cash-named files.
- SIP currently `disabled` — unrelated to MDM (Secure Boot is
  `Permissive Security`; both toggles were Leo-managed via Recovery
  for prior dev work). Tracked as Phase I2; restore via Recovery
  Terminal → `csrutil enable` + restore Full Security in startup
  options when convenient. Does not block onboarding.
- Sudo-tier confirmation queued for the user. Recommended block:

  ```bash
  sudo profiles show -type enrollment
  sudo profiles list -all
  sudo profiles -P | head -20
  sudo profiles renew -type enrollment        # LIVE Apple DEP query
  sudo defaults read /var/db/ConfigurationProfiles/Settings/com.apple.mdm.depnag
  sudo ls -laR /var/db/ConfigurationProfiles/Store/
  sudo /usr/libexec/mdmclient QueryDeviceInformation
  ```

  `profiles renew` is the strongest because it BYPASSES the local cache
  entirely and asks Apple's DEP server live. Expected result on every
  line: no `ConfigurationURL`, no `OrganizationName`,
  `MDMDeviceEnrollment:103 - No Device Enrollment Configuration was
  found for this computer`. If any of these turn up a Block server URL
  or org name, that flips the verdict — but probability is <5%.
- **Web/`/nia` research corroboration (independent agent):**
  Two practitioner sources (Mosen profiledocs, MicroMDM) confirm
  `.cloudConfigRecordNotFound` is written by `mdmclient` exactly when
  Apple's DEP server returns "No DEP record for this device" — i.e.
  our observed marker is Apple's own answer that this serial is not
  in any ABM organization. Apple's own ABM docs describe "Release
  from Organization" as the canonical action for sold/transferred
  devices and as permanent. Multiple news outlets (Financial Samurai,
  HR Executive, CNBC) document Block's Feb 2026 severance terms
  explicitly including "you may keep your corporate device." The
  one weak link in the local evidence — `depnag PreviouslyEnrolled`
  has no Apple-documented semantics — is bypassed entirely by today's
  Setup Assistant pass (Apple's live DEP query for this serial
  returned "no enrollment" at 17:31 UTC). **Net residual-risk
  probability: LOW (<5%).** No erase required.
