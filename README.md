<p align="center"><img src="assets/vidux-banner.svg" alt="Vidux banner: the five-step loop an agent runs each session — READ the plan and proof, ASSESS what's next, ACT on the smallest slice, VERIFY with real proof, CHECKPOINT a resume point — and the next run starts again at READ." width="100%" /></p>

<p align="center">
  <a href="https://github.com/firstbitelabsllc/vidux/actions/workflows/ci.yml"><img src="https://github.com/firstbitelabsllc/vidux/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" /></a>
  <img src="https://img.shields.io/badge/python-%E2%89%A53-3776ab?style=flat" alt="Python ≥ 3" />
</p>

# Vidux

One calm, local view of AI-assisted project work: the outcome, what is happening
now, a place to change direction, and proof. One `PLAN.md` keeps it durable.

## Install

Needs Bash, Git, and Python 3. Node is only for contributor tests and docs.

```bash
git clone https://github.com/firstbitelabsllc/vidux.git
cd vidux
mkdir -p "$HOME/.local/bin"
ln -sfn "$(pwd)/bin/vidux" "$HOME/.local/bin/vidux"
export PATH="$HOME/.local/bin:$PATH"
vidux doctor
```

## Quick start

```bash
cd /path/to/your/project
vidux init --here    # creates PLAN.md only if missing
vidux status
vidux browse         # local cockpit (loopback by default)
```

The browser opens one Outcome card. Projects, diagnostics, and the full plan
stay tucked away. A Steer stays local; it does not send chat or launch a model.
`vidux status` scans `VIDUX_DEV_ROOT` (default `~/Development`). [Config](vidux.config.example.json).

<p align="center"><img src="assets/vidux-dashboard.png" alt="Vidux desktop view showing one project outcome, the current move, a local Change direction box, and collapsed proof details." width="900" /></p>

<p align="center"><img src="assets/vidux-mobile.png" alt="The same Vidux outcome view on a phone, stacked in reading order: outcome, current move, steering, then proof details." width="390" /></p>

The card answers: What is the outcome? What is happening now? Does the work need
me? Where is the proof? Open **See proof and plan details** for evidence and the
full plan. `PROOF MISSING` remains explicit until evidence exists.

## Agent skill

Root [`SKILL.md`](SKILL.md) is the agent entry. Claude Code is the tested host;
other hosts are untested. Mount with
`ln -sfn /path/to/vidux "$HOME/.claude/skills/vidux"`.

## Where Vidux stops

Vidux does not schedule agents, route models, execute workers, or hold provider
credentials. Vidux can record provider-neutral claims, but it never launches a
provider or selects a model. The dashboard and optional checkpoint ledger are
local; neither replaces the repository plan.

`vidux checkpoint` requires proof text before completing a row and leaves its
plan edit uncommitted unless `--commit` is explicit.

## Outcome / Ask / Steer interchange

Vidux `1.2.0` includes provider-neutral JSON for one Outcome, an exceptional Ask,
Steers, and proof references. That interchange is separate from the local GUI:
neither is a worker runtime, shared-memory layer, or live model-steering claim.

```bash
python3 scripts/vidux-outcome-validate.py \
  --input examples/outcome-ask-steer/example.json
```

The read-only validator emits deterministic JSON: exit `0` valid, `1` invalid,
or `2` invocation/I/O failure. See the [contract](docs/reference/outcome-ask-steer.md)
and [schema](schemas/outcome-ask-steer.v1.json).

## Docs

Root is install + agent entry; deeper material stays in docs:
[Architecture](docs/doctrine/ARCHITECTURE.md) · [Doctrine](docs/doctrine/DOCTRINE.md) · [Loop](docs/doctrine/LOOP.md) · [Enforcement hooks](docs/doctrine/ENFORCEMENT.md) · [Core boundary](docs/CORE-CUT.md) · [Evidence format](guides/evidence-format.md) · [Site / guides](docs/)
Community: [CONTRIBUTING](CONTRIBUTING.md) · [SECURITY](SECURITY.md) · [SUPPORT](SUPPORT.md) · [CODE_OF_CONDUCT](CODE_OF_CONDUCT.md)
Repo `PLAN.md` (if present) is this repo's internal queue, not required to use Vidux in your project.

## Release truth

`VERSION` marks `1.2.0`. A release is valid only when its tag and GitHub Release
resolve to the same commit; there is no npm package. The historical
[`v1.1.1` release](https://github.com/firstbitelabsllc/vidux/releases/tag/v1.1.1)
remains unchanged. This release adds the Outcome-first local view without
turning Vidux into a model runner or hosted control plane.

## Contributing

```bash
npm ci
npm run verify
```
MIT licensed.
