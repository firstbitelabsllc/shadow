<p align="center"><img src="assets/vidux-banner.svg" alt="Vidux banner: the five-step loop an agent runs each session — READ the plan and proof, ASSESS what's next, ACT on the smallest slice, VERIFY with real proof, CHECKPOINT a resume point — and the next run starts again at READ." width="100%" /></p>

<p align="center">
  <a href="https://github.com/firstbitelabsllc/vidux/actions/workflows/ci.yml"><img src="https://github.com/firstbitelabsllc/vidux/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" /></a>
  <img src="https://img.shields.io/badge/python-%E2%89%A53-3776ab?style=flat" alt="Python ≥ 3" />
</p>

# Vidux

Local-first plan, proof, and resume contract for AI coding work across sessions, agents, or days.

One `PLAN.md` holds the queue, decisions, and progress. Agents read it, do one task,
write proof, and exit. Chat is not the control plane.

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

`vidux status` scans `VIDUX_DEV_ROOT` (default `~/Development`) and still shows your
current `PLAN.md` if that directory is missing. Options: `vidux help <command>`.
Config: [`~/.config/vidux/vidux.config.json`](vidux.config.example.json).

<p align="center"><img src="assets/vidux-dashboard.png" alt="The vidux browse cockpit: one project's PLAN.md at 67% with the declared current goal, the next step, and a results panel reading 0 winning / 0 losing / 1 unproven. The in-progress measure shows baseline, current, and target — and PROOF MISSING in red twice, because no artifact is attached yet. The header reads NET VALUE NOT PROVEN." width="900" /></p>

The loopback cockpit scans your dev root for plans. `PROOF MISSING` means a measure
and `NET VALUE NOT PROVEN` header stay unproven until an artifact is attached.

## Agent skill

Root [`SKILL.md`](SKILL.md) is the agent entry. Claude Code:

```bash
ln -sfn /path/to/vidux "$HOME/.claude/skills/vidux"
# or: claude --plugin-dir /path/to/vidux
```

Claude Code is the tested host. Agents that read [`SKILL.md`](SKILL.md) and plain
files can follow the contract; other hosts are untested.

## Where Vidux stops

Vidux does not schedule agents, route models, execute workers, or hold provider
credentials. Vidux can record provider-neutral claims, but it never launches a provider
or selects a model. The dashboard is local, not hosted.

## Outcome / Ask / Steer interchange

Vidux `1.1.0` adds a provider-neutral JSON contract for one Outcome, an
exceptional Ask, Steers, and proof references. It is an interchange boundary,
not a GUI, worker runtime, shared-memory layer, or live-steering claim.

```bash
python3 scripts/vidux-outcome-validate.py \
  --input examples/outcome-ask-steer/example.json
```

The read-only validator emits deterministic JSON: exit `0` valid, `1` invalid,
or `2` invocation/I/O failure. See the [contract](docs/reference/outcome-ask-steer.md)
and [schema](schemas/outcome-ask-steer.v1.json).

## Docs

Root is install + agent entry; deeper material stays in docs:
[Architecture](docs/doctrine/ARCHITECTURE.md) · [Doctrine](docs/doctrine/DOCTRINE.md) · [Loop](docs/doctrine/LOOP.md) · [Enforcement hooks](docs/doctrine/ENFORCEMENT.md) · [Core-cut handoff](docs/CORE-CUT.md) · [Evidence format](guides/evidence-format.md) · [Site / guides](docs/)
Community: [CONTRIBUTING](CONTRIBUTING.md) · [SECURITY](SECURITY.md) · [SUPPORT](SUPPORT.md) · [CODE_OF_CONDUCT](CODE_OF_CONDUCT.md)
Repo `PLAN.md` (if present) is this repo's internal queue, not required to use Vidux in your project.

## Release truth

Version `1.1.0` is the current source contract (`VERSION` + matching git tag);
there is no npm package on the registry. Install from source at the tagged tip
(`git checkout v1.1.0`) or track `main`. [Release notes](https://github.com/firstbitelabsllc/vidux/releases/tag/v1.1.0).

## Contributing

```bash
npm ci
npm run verify
```

MIT licensed.
