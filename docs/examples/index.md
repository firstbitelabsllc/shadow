# Examples

The repo ships worked example directories under `examples/`. This page maps them into the docs site.

## Included examples

### Bug fix lifecycle

`examples/bug-fix-lifecycle/README.md` is a minimal start-to-finish walk-through:

- gather evidence
- write a `PLAN.md`
- execute one task
- verify
- checkpoint

It is the smallest concrete example of the plan-first cycle in this repo.

### Outcome / Ask / Steer interchange

`examples/outcome-ask-steer/example.json` is a synthetic example of the
provider-neutral interchange schema. The neighboring invalid fixture exercises
the public-data boundary.

Validate either file directly:

```bash
python3 scripts/vidux-outcome-validate.py \
  --input examples/outcome-ask-steer/example.json
```

The schema and validator prove bounded data shape only. They do not implement a
GUI, persistence, worker execution, or live steering.

## When to use these examples

- Read the bug-fix example if you are new to Vidux and want the smallest
  plan/proof/resume cycle.
- Read the interchange example when integrating a read-only status surface.
- The `## Drift Log` section records planned-vs-actual deviations manually (see `docs/reference/plan-fields.md`).

## Related docs

- [Quick Start](/guide/quickstart) explains the first interactive cycle.
- [Outcome / Ask / Steer](/reference/outcome-ask-steer) defines the interchange
  boundary.
