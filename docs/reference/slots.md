# Extension slots — the named capabilities the Method plugs into

A **slot** is a named capability Shadow's method assumes it can reach, plus
the default thing that fills it. This file is a declaration, never a record:
nothing here is stamped, fetched, installed, or updated by any command.
`shadow doctor` resolves every line at read time and reports present, absent, or
stale — the same law as milestone status, which is derived at read time and
never stored.

Shadow runs correctly with every slot empty. A slot says what the method
would use if it were there; it never gates a cycle, claims a checkpoint, or
carries proof. The computer board owns coordination and entity `PLAN.md` files
own milestone/checkpoint detail and proof.

Override one binding with `SHADOW_SLOT_<NAME>` — an absolute path, or `off`
to say the emptiness is deliberate. Flags and environment stay authoritative;
there is no slot configuration file.

## The slots

- slot memory | kind: skill | default: memory | fills: routed recall — the routing file that delegates where to look things up (static docs, semantic vectors, graph — per person); recall is a lead, never plan, proof, or ownership authority; re-verify at the attributed source | absent: mount a skill named memory in one of the three skill roots, or set SHADOW_SLOT_MEMORY=off
- slot taste | kind: skill | default: taste | fills: the finished-quality grade on a human-visible surface and the voice of everything written or shown for humans — prose, briefs, PR text, explanation visuals — after it works and before anyone calls it done | absent: mount a skill named taste in one of the three skill roots, or set SHADOW_SLOT_TASTE=off
## How each kind resolves

**pack** — a multi-skill plugin installed by a host's own plugin system (no
shipped slot uses this kind today; the machinery retires next train if none
appears). Read
`~/.claude/plugins/cache/*/<default>/*/.claude-plugin/plugin.json` and compare
its `name`. Present when it matches, and the detail is that manifest's
`version`. One host surface only: Codex and Cursor plugin roots are not
asserted, for the same reason doctor gives about Cursor user rules — asserting a
path there would invent a convention.

**skill** — one skill mounted in the three roots the installer writes. Look for
`<root>/<default>/SKILL.md`. Present when at least one resolves.

A slot names only a capability Shadow itself reaches for. It never asserts
anything about the rest of a machine: which memory backend or model tooling a
person runs is their own configuration, and a check that failed over it would be
Shadow policing software it does not use. The memory slot reaches only for the
routing file it names — never the backend behind it.

## What doctor reports

| | pack | skill |
|---|---|---|
| present | PASS | PASS |
| absent | WARN, printing this line's `absent:` text | WARN, same |
| stale | FAIL | FAIL |
| `off` | PASS, naming the variable | PASS, same |

**Absent never fails.** A slot is an optional capability; a machine that has
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
and falls back to the native host plus Shadow Method. An optional slot can
never abort a resume packet.

Install adds no code: the declaration ships committed, so cloning defaults it.
