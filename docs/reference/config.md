# Configuration

Command-line flags and environment variables remain authoritative for runtime
behavior. A repository may also commit one optional `shadow.yaml` at its Git
root. The file is declaration only: it stores no resolved state, gates no
cycle, and never selects a provider, model, account, or credential. A repository
without it behaves exactly as before.

The supported declarations remain intentionally narrow:

```yaml
version: 1
adversarial-lenses: thermo, ponytail
```

`shadow config --explain` reports whether that repository declaration or the
built-in version 1 defaults are active, and prints the active adversarial lens
set. The default is `thermo, ponytail`; a repository may name one to eight
unique two-to-32-character lowercase slug names. The declaration records
review intent only: it does not install a skill, create a role or seat, route
work, or gate a cycle.
The command is read-only and creates no local state. Later schema additions
must retain the same absence behavior.

The review step itself is [attack, then refute](method.md#attack-then-refute).

## What may become a dial

The schema is narrow on purpose, so "make the method configurable" needs a test
rather than a preference. One test decides it:

> **A method dial may be declared only when a wrong value costs quality, never
> truth.**

A wrong quality setting degrades loudly — a weaker review, a slower train, a
bloated plan — and the person sees it. A wrong truth setting degrades silently:
the output still looks like a receipt, and nobody can tell it is worthless. The
asymmetry, not the topic, is what decides.

Every dial that exists, is plausible, or has been refused, classified by name:

| Candidate | A wrong value costs | Verdict |
|---|---|---|
| `adversarial-lenses` | a weaker review | **declared** — the shipped key |
| verification-tier thresholds | a release train that runs early or late | candidate |
| hot-plan budgets | plan bloat, or a premature archive | candidate |
| the three proof classes (`cmd`, `read`, `gate`) | a completion nobody proved | **fixed** |
| `shadow accept` as the only cmd-proof flip path | the same, one step earlier | **fixed** |
| bucket bindings | a capability silently resolving to the wrong thing | **fixed — environment only.** `SHADOW_BUCKET_*` is evaluated fresh; a committed file asserting presence can drift. See [buckets.md](buckets.md), which states there is no bucket configuration file |
| a memory or recall binding | recall mistaken for authority | **refused (~noks).** Which recall or memory tooling a person runs is their own configuration; Shadow neither reads it nor asserts anything about it |
| provider, model, account, or credential | the same class as a memory binding, plus a leak surface | **refused (~noks)** — see the closing rule below |

A candidate is not a promise. It says only that the dial *could* be declared if
someone shows the current key cannot express it.

These environment variables provide runtime defaults:

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
| `SHADOW_TELEMETRY` | Set exactly to `local` to append closed, local-only lifecycle events beneath the current project's `.shadow/evidence/`; unset and every other value write nothing. |

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
