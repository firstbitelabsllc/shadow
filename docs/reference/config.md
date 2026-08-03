# Configuration

Command-line flags are authoritative. These environment variables provide the
same defaults without another configuration file:

| Variable | Meaning |
|---|---|
| `PILOT_PUPPY_ROOT` | Installed repository root. |
| `PILOT_PUPPY_DEV_ROOT` | Default `status` and `browse` scan root. |
| `PILOT_PUPPY_BROWSER_HOST` | Loopback bind host. |
| `PILOT_PUPPY_BROWSER_PORT` | Browser port; default `7191`. |
| `PILOT_PUPPY_CODEX_BIN` | Optional Codex executable override. |
| `PILOT_PUPPY_CLAUDE_CODE_BIN` | Optional Claude Code executable override. |
| `PILOT_PUPPY_CURSOR_BIN` | Optional Cursor executable override. |

Provider logins remain in their native tools.
