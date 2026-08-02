# Pilot Puppy — the calm work conductor

Pilot Puppy is the product umbrella for one calm place that says what is
happening and what you can do next. **Vidux** remains the existing public
repository and durable core during migration; it is not a competing product.

## One product, four responsibilities

- **Vidux core** keeps the durable `PLAN.md`, Outcome / Ask / Steer state, proof,
  and resume boundary.
- **Chief of Staff** is the default briefing: what changed, what matters, what
  is blocked or uncertain, what Leo needs to do, and what Pilot Puppy recommends.
  It reports; it does not execute or become another authority.
- **Pilot Puppy driver** is the hidden right hand: it turns an outcome into a
  bounded packet, dispatches work, supervises the native host, and accepts or
  rejects the receipt before folding it back to the plan.
- **90** is the on-the-go client: it reads the brief, offers at most
  three choices, and forwards the selected Steer. It does not code, route
  providers, watch in the background, or keep a second queue.

Native Codex, Claude Code, and Cursor remain the execution hosts. The Mac is the
execution and credential boundary.

Pilot Puppy keeps the words human: **Outcome** means “what you want,” **Now** means
"what's happening," **Ask** means “needs your choice,” **Steer** means “change
direction,” and **Proof** means “why Pilot Puppy says it's done.” The brand can
be warm—“Pilot Puppy is checking the proof”—but never replaces the action or
hides a blocked state.

## Friendly name, stable contract

The maintainer entry point remains `/pilot` in a skill host and `pilot` in a
local shell. Pilot Puppy is the product name around that one front door; it is
not a second slash command or executable. The `pilot.*` schemas and `PILOT_*`
environment names remain stable. This is an additive product layer; it does not
rewrite history, rename the repository in this cycle, or create a second
runtime.

## Distribution without an install ritual

The canonical implementation is local because local custody is part of Pilot
Puppy's product promise. A future release may also expose thin, optional Pilot
Puppy interfaces in ChatGPT, Claude, or Cursor marketplaces so a non-technical
person can discover the workflow without cloning a repository or installing npm
packages.

Those interfaces may read typed status and submit a typed Ask or Steer over a
private local/tailnet connection. They must not:

- execute code or choose providers in the cloud;
- receive source files, credentials, raw transcripts, or personal paths; or
- create a second plan, queue, ledger, or acceptance authority.

The hosted surface is therefore a friendly remote control, not a hosted copy of
the computer. If the local boundary is unavailable, it reports offline or
blocked; it does not pretend that a message was dispatched.

This document describes the target distribution boundary. The flagship plan's
ordered gates still govern implementation and release; no hosted wrapper is
claimed as shipped until it has its own privacy, offline, and receipt tests.
