# Configuration

Shadow has two deliberately separate scopes. An entity repository's ignored
`.shadow/local.yaml` may declare behavior preferences and assert which computer
board it expects. The installed Shadow checkout's ignored
`.shadow/machine.yaml` is the single machine bootstrap: it may select the one
computer board and declare top-level host-directive topology. An ambient entity
repository can never redirect either machine authority.

Both files are machine-local, ignored, and untracked. A repository may track a
reviewed example, but an example is never effective merely because it exists.
Declarations are preferences and topology, never resolved state: no cache,
timestamp, installation record, claim, task, proof, provider binding,
credential, or observed Cursor state is written from configuration. Missing
configuration preserves built-in behavior.

Run `shadow config --init-local` once to copy the repository's reviewed
`shadow.example.yaml` (or Shadow's shipped template when the consumer has no
repository-specific example) into `.shadow/local.yaml`. Initialization first
adds `/.shadow/local.yaml` to that checkout's Git exclusion, never edits the
tracked `.gitignore`, never runs `git add`, and never overwrites an existing
local file. `shadow config --explain` names the recommended and effective
surfaces and prints the effective values. A tracked, symlinked, or Git-visible
effective file fails closed rather than becoming publishable configuration.

In the installed Shadow checkout, run `shadow config --init-machine` to copy
`shadow.machine.example.yaml` into ignored `.shadow/machine.yaml` and
`shadow config --explain-machine` to inspect that scope. Machine and entity
files can coexist there without either loader accepting the other scope's
keys.

The supported file shape is a strict YAML subset: nested mappings, scalar
values, and scalar lists with two-space indentation. Unsupported YAML is
refused with the filename and line instead of being guessed.

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

The mapping key under `leads` is the durable claim-owner identity; each entry
supplies only a display name and lens preferences. An unlisted seat remains
legal and signs claims under the command's `--by` value. `buckets` declares optional
capability bindings. `durability` bounds claim return time; it does not create a
heartbeat or scheduler. Provider, model, account, credential, token, host-route,
and legal-seat selectors are refused anywhere in the document.

An entity may assert the already-selected board without gaining authority to
choose another one:

```yaml
computer:
  expected_board_root: ~/private/shadow-board
```

The installed Shadow checkout alone may carry the machine bootstrap:

```yaml
version: 1
board:
  root: ~/private/shadow-board
directives:
  source: /absolute/private/path/to/AGENTS.md
  targets:
    claude: ~/.claude/CLAUDE.md
    codex: ~/.codex/AGENTS.md
  projections:
    cursor: user_rules
```

Claude and Codex targets must already resolve to the canonical `source`;
Shadow refuses mismatches and never creates or repoints personal links. Cursor
is an explicit User Rules projection, not a file target. Shadow derives the
expected standing-goal hash but cannot inspect Cursor's application setting
and never stores observed or expected hashes in YAML.

Explicit command-line flags remain authoritative. Environment variables are
machine-local overrides; `.shadow/local.yaml` supplies checkout-local
preferences copied from a reviewed recommendation; built-ins are the final
fallback:

```text
flag > environment > .shadow/local.yaml > built-in default
```

These environment variables remain available:

| Variable | Meaning |
|---|---|
| `SHADOW_ROOT` | Installed repository root. |
| `SHADOW_PORTFOLIO_ROOT` | Canonical bounded import root for `status` and `browse`; defaults to `~/Development`. |
| `SHADOW_BROWSER_HOST` | Loopback bind host. |
| `SHADOW_BROWSER_PORT` | Browser port; default `7191`. |
| `SHADOW_BROWSER_QUIET` | Set to `1` to suppress loopback request logs. |
| `SHADOW_PYTHON` | Optional Python 3.10+ interpreter override; the CLI, browser launcher, and Python gates resolve a compatible versioned interpreter from PATH when unset. |
| `SHADOW_CODEX_BIN` | Optional Codex executable override. |
| `SHADOW_CLAUDE_CODE_BIN` | Optional Claude Code executable override. |
| `SHADOW_CURSOR_BIN` | Optional Cursor executable override. |

Provider logins remain in their native tools.

Shadow also keeps bounded local evidence in `.shadow/` inside each project.
The initializer protects only `.shadow/local.yaml` through the checkout's
local Git exclusion; it does not claim custody of other `.shadow/` contents.
An explicit `git add -f` can override any Git ignore, so every config consumer
also refuses the effective path if it appears in the index. Like other ignored
checkout-local files, the override does not survive `git clean -fdx`; the
tracked example is the recovery source.

The computer authority is `<configured board root>/board.json`, defaulting to
`~/.shadow/board.json`, inside its own local Git repository. It groups entity-plan pointers by project, stores global project
priority, one resume checkpoint per entity, and claims/owners—never checkpoint
text, proof, or evidence. No remote
is required or pushed automatically. A separately configured private remote
may be pushed explicitly as lagging recovery; it never gates a local write or
becomes authority.


Never place provider/model/account/quota details in a plan, browser
briefing, status output, or receipt; which provider a native host uses is the
host CLI's own business.
