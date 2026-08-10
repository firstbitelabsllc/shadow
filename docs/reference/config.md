# Configuration

Shadow reads at most one checked-in `shadow.yaml` at the current Git repository
root. Its declarations are preferences, never resolved state: no cache,
timestamp, installation record, claim, task, proof, provider binding, or
credential is written from configuration. A repository with no file behaves
identically through built-in defaults.

Use `shadow config --explain` to print the effective values and whether they
came from `shadow.yaml` or built-in defaults. The supported file shape is a
strict YAML subset: nested mappings, scalar values, and scalar lists with
two-space indentation. Unsupported YAML is refused with the filename and line
instead of being guessed.

```yaml
version: 1
leads:
  codex:
    display_name: Codex
    default_lenses:
      - integration
      - crash_recovery
method:
  adversarial_lenses:
    - assumptions
    - correctness
    - integration
    - crash_recovery
    - privacy
    - stranger_install
buckets:
  taste: taste
  future: future
durability:
  claim_return_minutes: 480
```

`leads` supplies display names, handles, and lens preferences only. An unlisted
seat remains legal and signs claims normally. `buckets` declares optional
capability bindings. `durability` bounds claim return time; it does not create a
heartbeat or scheduler. Provider, model, account, credential, token, host-route,
and legal-seat selectors are refused anywhere in the document.

Explicit command-line flags remain authoritative. Environment variables are
machine-local overrides; configuration supplies reviewed repository defaults;
built-ins are the final fallback:

```text
flag > environment > shadow.yaml > built-in default
```

These environment variables remain available:

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
