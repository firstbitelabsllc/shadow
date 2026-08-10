# Extension buckets — the named slots the Method plugs into

A **bucket** is a named capability Shadow's method assumes it can reach, plus
the default thing that fills it. This file is a declaration, never a record:
nothing here is stamped, fetched, installed, or updated by any command.
`shadow doctor` resolves every line at read time and reports present, absent, or
stale — the same law as milestone status, which is derived at read time and
never stored.

Shadow runs correctly with every bucket empty. A bucket says what the method
would use if it were there; it never gates a cycle, claims a checkpoint, or
carries proof. The computer board owns coordination and entity `PLAN.md` files
own milestone/checkpoint detail and proof.

Override one binding with `SHADOW_BUCKET_<NAME>` — an absolute path, or `off`
to say the emptiness is deliberate. Flags and environment stay authoritative;
`.shadow/local.yaml` may bind a declared bucket to another skill/pack name or to
`off`. The declaration remains the catalog and default; the config is a
reviewed repo preference and never stores whether resolution succeeded.

## The buckets

- bucket superpowers | kind: pack | default: superpowers | fills: the process discipline inside every applicable claimed lane — brainstorm before building, test first, review, and verify before claiming done. Shadow owns the durable plan and keeps the full Outcome moving | absent: install superpowers from the claude-plugins-official marketplace, or set SHADOW_BUCKET_SUPERPOWERS=off
- bucket honcho | kind: builtin | default: docs/reference/honcho.md | fills: durable memory of what the work is trying to achieve, and continuity across CLIs, providers, and machines — carried by PLAN.md and git, never by an installed store | absent: unreachable; a builtin bucket ships filled by this repository
- bucket taste | kind: skill | default: taste | fills: the finished-quality grade on a human-visible surface, after it works and before anyone calls it done | absent: mount a skill named taste in one of the three skill roots, or set SHADOW_BUCKET_TASTE=off
- bucket future | kind: skill | default: future | fills: bounded successor-goal synthesis from this entity plan's append-only LESSON and DECISION Progress rows; it proposes no queue, runtime role, or memory store | absent: mount a skill named future in one of the three skill roots, or set SHADOW_BUCKET_FUTURE=off

The `superpowers` binding is leaf-only. The pack root is never selected. Shadow
may name only a concrete installed whole leaf from this compatible set:
`verification-before-completion`, `test-driven-development`,
`systematic-debugging`, and `receiving-code-review`. Brainstorm and
request-review ideas are adapted disciplines inside Shadow Method, not partial
or selected plugin leaves. `writing-plans`, `executing-plans`,
`dispatching-parallel-agents`, `subagent-driven-development`,
`using-superpowers`, `brainstorming`, and `requesting-code-review` are refused
even when explicitly requested. The same default-deny applies to every other
pack leaf not in the compatible set, including `using-git-worktrees`,
`finishing-a-development-branch`, and `writing-skills`: the computer board,
entity plan, and Shadow host-run keep those jobs. A pack with no compatible
whole leaf falls back to the native host plus Shadow Method. A generic pack
request also falls back; the milestone tools line must name matching TDD,
debugging, receiving-review, or verification intent before amp records that
installed leaf as source for a host-neutral Shadow Method adaptation. A
Claude-cache leaf is never printed as if Codex or Cursor could invoke it.
Raw `/superpowers` and refused leaf invocations are also removed from the
projected `TOOLS:` line; unrelated project tools remain unchanged.

## How each kind resolves

**pack** — a multi-skill plugin installed by a host's own plugin system. Read
`~/.claude/plugins/cache/*/<default>/*/.claude-plugin/plugin.json` and compare
its `name`. Present when it matches, and the detail is that manifest's
`version`. One host surface only: Codex and Cursor plugin roots are not
asserted, for the same reason doctor gives about Cursor user rules — asserting a
path there would invent a convention.

**skill** — one skill mounted in the three roots the installer writes. Look for
`<root>/<default>/SKILL.md`. Present when at least one resolves.

**builtin** — Shadow implements the pattern itself, so the slot ships filled and
must stay empty of an installed thing. Present when the named file exists and no
directory of that name sits in a skill root or the plugin cache. **Stale when an
installed namesake is found** — that is the point of this kind: it turns a
standing ruling into a mechanical refusal. Never absent.

## What doctor reports

| | pack | skill | builtin |
|---|---|---|---|
| present | PASS | PASS | PASS |
| absent | WARN, printing this line's `absent:` text | WARN, same | not reachable |
| stale | FAIL | FAIL | FAIL |
| `off` | PASS, naming the variable | PASS, same | PASS, same |

**Absent never fails.** A bucket is an optional capability; a machine that has
not installed one is not a broken install. Present-but-wrong does fail, on the
same reasoning the standing-goal check uses: a drifted copy is worse than none.

## Why this is not a second store

The file holds declaration only — no version stamp, no timestamp, no
`last_checked`, no `installed: true`. A file that stamps nothing cannot drift
from reality; it can only be wrong about intent, and wrong-about-intent is a
reviewed git edit. Contrast a plugin manager's `installed_plugins.json`, which
stores exactly the resolved state that *can* go stale.

Nothing coordinates through this file. `shadow throw`, `shadow accept`, and
`shadow status` never read it. `shadow amp` may resolve only capabilities that
the selected milestone explicitly named in `- tools:` and records the result
inside its optional handoff block; it writes no state and absence never blocks
the packet. Deleting this declaration therefore removes resolution detail, not
rows, claims, priority, proof, or resume.

Declaration or resolution exceptions follow the same optional law: amp records
a deterministic warning (exception type, never machine-specific error text)
and falls back to the native host plus Shadow Method. An optional bucket can
never abort a resume packet.

`future` is a skill bucket, not a runtime role. When a completed entity asks to
mint a successor, amp reads only that entity's append-only `## Progress`
`LESSON` and `DECISION` receipts, keeps a bounded deterministic tail, and writes
nothing. Tasks, Contradictions, other plans, and any external store remain out
of scope; the resulting context is input to the next goal, never coordination
state or acceptance proof.

Install adds no code: the declaration ships committed, so cloning defaults it.
