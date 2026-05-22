# Archived Tasks

Archived by `vidux-plan-gc.py`. Append-only — do not edit.
Tasks here are historical record; they were [completed] when archived.

## Archived 2026-05-22T01:59Z

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

- [completed] B1 `git clone leojkwan/ai` → `~/Development/ai`.
- [completed] B2 `git clone leojkwan/ai-leo` → `~/Development/ai-leo`.
- [completed] B3 `git clone leojkwan/vidux` → `~/Development/vidux`.
- [completed] B4 `git clone leojkwan/moussey` → `~/Development/moussey`.
- [completed] B5 Switch all four remotes from HTTPS to SSH.

- [completed] C1 Write `~/.ai/sources.list` with three lines (ai/skills,
  vidux, ai-leo/skills).
- [completed] C2 `bash ~/Development/ai/scripts/bootstrap.sh` → 71 skills
  active, three tool-roots symlinked, post-merge hook installed, ledger
  CLI shims in `~/bin/`.
- [completed] C3 Captain audit — green.

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

- [completed] E1 `brew upgrade node` 20.8.0 → 26.0.0 (Next.js 16 needs ≥20.9).
- [completed] E2 `cd ~/Development/moussey && npm install`.
- [completed] E3 `MOUSSEY_LAN_PEERS='Studio=...' MOUSSEY_SELF_NAME='M1 Max'
  MOUSSEY_AGENT_BACKEND=off ./scripts/moussey-home.sh --install`.
- [completed] E4 Verify moussey LaunchAgent running on `http://0.0.0.0:4321`.
- [completed] E5 Verify vidux-browser LaunchAgent running on
  `http://0.0.0.0:7191`.

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

