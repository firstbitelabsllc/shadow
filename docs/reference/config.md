# Configuration

Command-line flags are authoritative. A repository may also carry one
declaration-only file, `shadow.yaml`, at its Git root. It is a tracked project
file, intentionally separate from `.shadow/`, whose local evidence is often
ignored.

```yaml
buckets:
  taste: product-taste
leads:
  - name: editorial
    lenses:
      - accessibility
      - copy
```

Read it with `shadow config --repo .`; `--json` exposes the parsed declaration.
There is no fallback location: one repository, at most one `shadow.yaml`.

The reader accepts a deliberately small YAML subset: mappings, lists, plain
strings, and double-quoted strings with two-space indentation. Unsupported or
malformed syntax fails with `shadow.yaml` and a line number; it is never
silently treated as absent configuration.

The file declares preferences only. It does not select a provider, model,
account, credential, host, task, plan state, or runtime role. An unlisted lead
remains free to claim a task, and a config file never decides whether a claim
is legal. A machine with no `shadow.yaml` has the same flags, environment
defaults, command behavior, and routing behavior as before.

These environment variables provide defaults where a command exposes one:

| Variable | Meaning |
|---|---|
| `SHADOW_ROOT` | Installed repository root. |
| `SHADOW_DEV_ROOT` | Default `status` and `browse` scan root. |
| `SHADOW_BROWSER_HOST` | Loopback bind host. |
| `SHADOW_BROWSER_PORT` | Browser port; default `7191`. |
| `SHADOW_BROWSER_QUIET` | Set to `1` to suppress loopback request logs. |
| `SHADOW_PYTHON` | Optional Python 3.10+ interpreter override; the CLI, browser launcher, and npm gates resolve a compatible versioned interpreter from PATH when unset. |
| `SHADOW_CODEX_BIN` | Optional Codex executable override. |
| `SHADOW_CLAUDE_CODE_BIN` | Optional Claude Code executable override. |
| `SHADOW_CURSOR_BIN` | Optional Cursor executable override. |

Provider logins remain in their native tools. Never place provider, model,
account, quota, or credential details in `shadow.yaml`, a plan, browser
briefing, status output, or receipt.

Shadow keeps bounded local evidence in `.shadow/` inside each
project. Adding `.shadow/` to the project's `.gitignore` is recommended to
keep ordinary Git output quiet.


Never place provider/model/account/quota details in a plan, browser
briefing, status output, or receipt; which provider a native host uses is the
host CLI's own business.
