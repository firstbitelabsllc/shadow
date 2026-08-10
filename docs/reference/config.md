# Configuration

Command-line flags are authoritative. These environment variables provide the
same defaults without another configuration file:

| Variable | Meaning |
|---|---|
| `SHADOW_ROOT` | Installed repository root. |
| `SHADOW_PORTFOLIO_ROOT` | Canonical bounded import root for `status` and `browse`; defaults to `~/Development`. |
| `SHADOW_DEV_ROOT` | Legacy fallback only when `SHADOW_PORTFOLIO_ROOT` is unset. |
| `SHADOW_BROWSER_HOST` | Loopback bind host. |
| `SHADOW_BROWSER_PORT` | Browser port; default `7191`. |
| `SHADOW_BROWSER_QUIET` | Set to `1` to suppress loopback request logs. |
| `SHADOW_PYTHON` | Optional Python 3.10+ interpreter override; the CLI, browser launcher, and Python gates resolve a compatible versioned interpreter from PATH when unset. |
| `SHADOW_CODEX_BIN` | Optional Codex executable override. |
| `SHADOW_CLAUDE_CODE_BIN` | Optional Claude Code executable override. |
| `SHADOW_CURSOR_BIN` | Optional Cursor executable override. |

Provider logins remain in their native tools.

Shadow keeps bounded local evidence in `.shadow/` inside each
project. Adding `.shadow/` to the project's `.gitignore` is recommended to
keep ordinary Git output quiet.

The computer authority is `~/.shadow/board.json`, inside its own local Git
repository. It groups entity-plan pointers by project, stores global project
priority, one resume checkpoint per entity, and claims/owners—never checkpoint
text, proof, or evidence. No remote
is required or pushed automatically. A separately configured private remote
may be pushed explicitly as lagging recovery; it never gates a local write or
becomes authority.


Never place provider/model/account/quota details in a plan, browser
briefing, status output, or receipt; which provider a native host uses is the
host CLI's own business.
