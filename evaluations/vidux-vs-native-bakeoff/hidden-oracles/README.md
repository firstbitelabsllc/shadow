# Hidden Oracles

Each fixture gets a subdirectory named after `fixture_id`.

Minimum contents per fixture:

- `README.md`: what the hidden oracle checks and why it is fair.
- `run.sh`: deterministic command that exits non-zero on failure.
- `manifest.json`: list of hidden tests, mutation checks, and real-surface checks.
- optional fixtures/data needed by `run.sh`.

Rules:

- Hidden oracle content is not visible to runners during implementation.
- Hidden tests must target the fixture acceptance criteria, not arm-specific behavior.
- At least one seeded bad solution must fail the oracle before the full bake-off starts.
- If a hidden oracle is wrong, exclude all affected arm runs for that fixture and repair the oracle before rerun.

