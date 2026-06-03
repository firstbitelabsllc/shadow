# Vidux Five-Hour Observability And Config Plan

## Purpose

Turn Leo's five-hour Vidux push into a concrete, non-hot mega plan: find real bugs, improve docs, smoke multiple local app surfaces, and make lifecycle call stacks visible through signposts for Codex, Claude, Cursor, and spawned subagent work.

## Receipts

- `bin/vidux` already exposes `doctor` and `signpost`, but has no `config` command yet.
- `scripts/vidux_signpost.py` emits, wraps, and summarizes JSONL events, but does not yet render a call-stack trace for one run id.
- `scripts/vidux-doctor-cli.sh` checks fresh-clone install health and passes locally with `VIDUX_DOCTOR_SKIP_NPM_TEST=1`, but does not validate Vidux config shape.
- `docs/reference/config.md` says the checked-in live config includes top-level areas, while current source truth is `vidux.config.example.json`; live `vidux.config.json` is user-local and gitignored.
- `docs/reference/hooks.md` describes before/after task hooks, but does not show a signposted pre/during/post trace convention.
- `docs/reference/browser.md` documents the local browser at `http://127.0.0.1:7191`; browser smoke should stay local and loopback unless explicitly opened to LAN.

## Future Pre-Mortem

Technical landmines:

- A config CLI that parses JSON differently from `vidux-inbox-sync.py` or `resolve-plan-store.sh` will create a second source of truth.
- A signpost trace that only records aggregate counts will not prove the call stack Leo asked about.
- A doctor check that runs full test suites every time can become too slow to trust as a pre-hook smoke.
- Browser smoke can accidentally become a UI redesign rabbit hole; the first proof should be health, plan discovery, comments, and local note safety.

Process landmines:

- Five hours of bug hunting can devolve into doc-only bookkeeping. Each slice should ship a runnable helper, test, or smoke artifact.
- Product repos are tempting proof surfaces, but StrongYes/Resplit hot paths must stay observe-only unless a current plan row authorizes mutation.
- Captain boundaries matter: shared `/ai` skill changes are out of scope unless the bug is in the shared skill registry itself.

Self landmines:

- Vidux can over-improve itself instead of making the user's next terminal action easier.
- The goal names both CLI and browser UX; choose the CLI first when it proves config/doctor/signpost behavior, then improve browser only where it exposes that truth better.

## Five Questions We Were Not Asking

1. Can a fresh user run one terminal command to see which config Vidux is using and whether the shape is valid?
2. Can a hook or spawned subagent run produce a single trace proving `before -> during/spawn -> after` order?
3. Does `vidux doctor` validate the config file it depends on, or only the surrounding toolchain?
4. Does browser smoke prove plan discovery and write safety, or only that `/api/health` returns 200?
5. Are Codex, Claude, and Cursor lifecycle docs describing the same durable plan/ledger/signpost model, or three slightly divergent stories?

## First Slice

Ship the terminal proof path first:

1. `vidux config` for `path`, `show`, `check`, and safe `init`.
2. `vidux doctor` config-shape check.
3. `vidux signpost trace` to inspect ordered events for a run id.
4. Docs that show the pre/during/post signpost convention and config truth.
5. Smoke artifact proving config, doctor, and signpost trace on this machine.

## Non-Claims

- This does not enable CI fail-on enforcement.
- This does not mutate StrongYes, Resplit web, or Resplit iOS repos.
- This does not install hooks into user repos.
- This does not create external messages, GitHub PRs, or paid-service mutations.
- This does not claim the full five-hour goal is complete after the first slice.
