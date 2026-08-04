# Configuration

Command-line flags are authoritative. These environment variables provide the
same defaults without another configuration file:

| Variable | Meaning |
|---|---|
| `PILOT_PUPPY_ROOT` | Installed repository root. |
| `PILOT_PUPPY_DEV_ROOT` | Default `status` and `browse` scan root. |
| `PILOT_PUPPY_BROWSER_HOST` | Loopback bind host. |
| `PILOT_PUPPY_BROWSER_PORT` | Browser port; default `7191`. |
| `PILOT_PUPPY_BROWSER_QUIET` | Set to `1` to suppress loopback request logs. |
| `PILOT_PUPPY_PYTHON` | Optional Python 3.10+ interpreter override; the CLI, browser launcher, and npm gates resolve a compatible versioned interpreter from PATH when unset. |
| `PILOT_PUPPY_CODEX_BIN` | Optional Codex executable override. |
| `PILOT_PUPPY_CLAUDE_CODE_BIN` | Optional Claude Code executable override. |
| `PILOT_PUPPY_CURSOR_BIN` | Optional Cursor executable override. |
| `PILOT_PUPPY_ROSTER_FILE` | Optional path to a deliberately chosen local roster file. |
| `PILOT_PUPPY_TELEMETRY` | `off` by default; set exactly to `langfuse` to opt into metadata-only lifecycle observation. |
| `LANGFUSE_BASE_URL` | Explicit Langfuse endpoint used only when telemetry is enabled. |
| `LANGFUSE_PUBLIC_KEY` | Local Langfuse public key used only by the optional SDK. |
| `LANGFUSE_SECRET_KEY` | Local Langfuse secret key used only by the optional SDK. |

Provider logins remain in their native tools.

Telemetry is an optional observation seam, not Pilot Puppy's control plane. It
requires the separately installed `langfuse` Python package and all three
`LANGFUSE_*` variables above. It exports only the closed metadata schema in the
[privacy contract](privacy.md), after local evidence exists; it never exports
task or receipt content and never affects local behavior when unavailable.

The roster file is local setup data, not project evidence. Keep any personal
seat mapping outside repositories and never place provider/model/account/quota
details in a plan, browser briefing, status output, or receipt.
