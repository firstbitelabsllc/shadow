# Pilot Puppy inside Vidux

Pilot Puppy is Vidux's friendly internal name for the driver that takes an
outcome to an honest result. It is not a separate product or install choice.
Most people should only see **Vidux**: one calm place that says what is
happening and what they can do next.

## One product, three responsibilities

- **Vidux** keeps the durable `PLAN.md`, Outcome / Ask / Steer state, proof, and
  resume boundary.
- **Pilot Puppy** is the hidden right-hand driver: it turns an outcome into a bounded
  packet, dispatches work, supervises the native host, and accepts or rejects
  the receipt before folding it back to the plan.
- **90** is the on-the-go client: it reads a concise status, offers at most
  three choices, and forwards the selected Steer. It does not code, route
  providers, watch in the background, or keep a second queue.

Native Codex, Claude Code, and Cursor remain the execution hosts. The Mac is the
execution and credential boundary.

Vidux keeps the words human: **Outcome** means “what you want,” **Now** means
“what's happening,” **Ask** means “needs your choice,” **Steer** means “change
direction,” and **Proof** means “why Vidux says it's done.” Pilot Puppy can
provide a little warmth—“Pilot Puppy is checking the proof”—but never replaces
the action or hides a blocked state.

## Friendly name, stable contract

Maintainers may use `/pilot-puppy` in a skill host or `pilot-puppy` in a local
shell. Existing `/pilot` and `pilot` callers remain supported as compatibility
aliases, and the `pilot.*` schemas and `PILOT_*` environment names remain
stable. This is an additive brand layer; it does not rewrite history or create
a second runtime. End users do not need to learn this name.

## Distribution without an install ritual

The canonical implementation is local because local custody is part of Vidux's
product promise. A future release may also expose thin, optional Vidux
interfaces in ChatGPT, Claude, or Cursor marketplaces so a non-technical person
can discover the workflow without cloning a repository or installing npm
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
