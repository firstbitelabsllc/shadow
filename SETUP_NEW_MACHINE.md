# Vidux — New Machine Setup

> Run these steps on any new computer to get Vidux's cross-tool compaction
> and agent teams working. Takes ~5 minutes.

## 1. Claude Code (`~/.claude/settings.json`)

These settings should already exist if you've synced your dotfiles.
Verify or add:

```json
{
  "env": {
    "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "50",
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  },
  "hooks": {
    "PreCompact": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Compaction imminent. Critical context should already be in files (PLAN.md, .agent-ledger/). If working in a loop, ensure current iteration state is checkpointed to disk before compaction summarizes conversation history.'"
          }
        ]
      }
    ],
    "PostCompact": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Context compacted. Rehydrate from repo files: PLAN.md, CLAUDE.md, .agent-ledger/activity.jsonl. Do not rely on pre-compaction conversation details — they are lossy summaries now.'"
          }
        ]
      }
    ]
  }
}
```

**What each setting does:**
- `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=50` — fires compaction at 50% context (not the default 85-90%). Gives the summarizer room for a high-quality summary.
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` — enables Agent Teams. Each teammate gets its own context window. Natural fit for Vidux's fan-out pattern (4 research agents -> 1 synthesizer -> 1 critic).
- `PreCompact` hook — reminds the agent to checkpoint state to disk before compaction fires.
- `PostCompact` hook — reminds the agent to rehydrate from disk files, not trust the compressed summary.

### 1b. Status Line

The status line shows context headroom at a glance: `45% until compact · Claude Sonnet 4.6`.

```bash
# Install the script (adjust source path to wherever you cloned vidux)
cp /path/to/vidux/scripts/statusline.sh ~/.claude/statusline.sh
chmod +x ~/.claude/statusline.sh
```

Then add to `~/.claude/settings.json` (use your actual username — no tilde):

```json
{
  "statusLine": {
    "type": "command",
    "command": "/Users/YOUR_USER/.claude/statusline.sh",
    "padding": 2
  }
}
```

**Why no tilde:** Claude Code does not shell-expand `~/` in command paths. Using `~/.claude/statusline.sh` silently falls back to the built-in status bar. Always use the absolute path.

## 2. Codex CLI (`~/.codex/config.toml`)

Add these lines to your existing config:

```toml
# Compaction: fire at ~75% of context window (272k * 0.75 = 204k)
model_auto_compact_token_limit = 200000

# Multi-agent support
[features]
multi_agent = true
```

**Why 200k, not matching Claude's 50%?**
Codex's server-side compaction (`/v1/responses/compact`) produces higher-quality summaries than local compaction, so we can afford a later trigger. 75% is the sweet spot — 85-90% is too late (compaction can fail to fire), 50% wastes context.

**Codex has no PreCompact/PostCompact hooks** (lifecycle hooks are feature-flagged and unstable as of April 2026). The workaround is Vidux discipline:
- One owned mission/lane per Codex session
- Write PLAN.md before code changes
- Keep pushing that same lane until you hit a verified checkpoint or a real blocker
- After checkpoint, end cleanly instead of trusting compaction memory

## 3. Codex App (Desktop)

The desktop app shares `~/.codex/config.toml` settings, but:
- Auto-compaction is buggy (hangs, triggers too often)
- No `/compact` manual trigger yet
- No model-aware settings (switching models can break thresholds)

**Recommendation:** Use Codex CLI for Vidux work, not the desktop app. The desktop app is fine for quick one-off questions but not for plan-first long-horizon work.

## 4. Skills Directory (`~/.claude/skills/`)

The Vidux skill lives in its own repo. On a new machine:

```bash
# Clone the canonical repo:
git clone git@github.com:leojkwan/vidux.git ~/Development/vidux

# Symlink into Claude Code's skills directory:
ln -sf ~/Development/vidux ~/.claude/skills/vidux
```

Verify the skill loads: start a Claude Code session and type `/vidux` — it should activate.

## 5. Verification Checklist

```bash
# Claude Code
grep AUTOCOMPACT ~/.claude/settings.json     # should show "50"
grep AGENT_TEAMS ~/.claude/settings.json     # should show "1"
grep PreCompact ~/.claude/settings.json      # should exist
grep PostCompact ~/.claude/settings.json     # should exist

# Codex CLI
grep auto_compact ~/.codex/config.toml       # should show 200000
grep multi_agent ~/.codex/config.toml        # should show true

# Skills
ls ~/.claude/skills/vidux/SKILL.md           # should exist

# Status line
test -x ~/.claude/statusline.sh && echo "OK" || echo "MISSING"
jq '.statusLine.command' ~/.claude/settings.json  # should be absolute path
```

## Cross-Tool Compaction Summary

| Tool | Threshold | Hooks | Session Discipline |
|------|-----------|-------|--------------------|
| Claude Code | 50% context | PreCompact + PostCompact (reliable) | Multi-task OK with checkpoints |
| Codex CLI | 200k tokens (~75%) | Feature-flagged (unreliable) | One task per session, strict |
| Codex App | Same as CLI | None | Avoid for plan-first work |
