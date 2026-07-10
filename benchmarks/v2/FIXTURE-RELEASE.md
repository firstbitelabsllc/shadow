# Benchmark v2 Fixture Release

This is an evaluator procedure, not an arm prompt. It converts public fixture
files and evaluator-only oracle files into an immutable release that the
benchmark runner can verify without exposing an oracle body to any arm.

## Boundary

- `manifest.json` stays frozen with every oracle marked `pending_seal`.
- The public fixture root contains only files that may be copied into an arm
  workspace.
- The evaluator-only oracle root is a separate, non-overlapping directory.
- The release output contains fixture SHA-256 values and oracle SHA-256
  commitments, never oracle paths or oracle bytes.
- The release binds the exact source-manifest digest. Changing a threshold,
  arm, metric, or source manifest invalidates the release.
- A release is immutable. The command refuses to overwrite an existing output.

The release is not a benchmark result. It only makes a real paired run
possible. No run packet may be issued until every scenario reaches its frozen
fixture target and every public fixture hash verifies.

## Evaluator Index

Keep this index with the evaluator, outside the source checkout and every arm
workspace. Paths are relative to their corresponding roots.

```json
{
  "release_id": "v2-r1",
  "evaluator_receipt_id": "evaluator-receipt-20260710-r1",
  "fixtures": [
    {
      "scenario_class": "durable_state",
      "fixture_id": "durable-01",
      "fixture_path": "durable_state/durable-01.json",
      "oracle_path": "durable_state/durable-01.json"
    }
  ]
}
```

The full index needs at least 12 unique fixtures for each of these classes:
`durable_state`, `interruption_recovery`, `cross_project_prioritization`, and
`proof_inspection`.

## Seal And Verify

```bash
python3 scripts/vidux-benchmark-v2.py seal-release \
  --fixture-root /path/to/public-fixtures \
  --oracle-root /path/to/evaluator-oracles \
  --index /path/to/evaluator-index.json \
  --output /path/to/v2-r1-release.json

python3 scripts/vidux-benchmark-v2.py readiness \
  --release /path/to/v2-r1-release.json \
  --fixture-root /path/to/public-fixtures
```

`readiness` exits zero only when the source manifest, release metadata, and
every public fixture byte all match. It rejects relative-path escape, symlink
traversal, overlapping fixture and oracle roots, an incomplete scenario class,
or a changed fixture.

## Arm Packet

After readiness passes, the runner verifies the named public fixture, copies it
into a fresh identical workspace for each arm, then asks Vidux for its
read-only packet:

```bash
python3 scripts/vidux-benchmark-v2.py packet \
  --release /path/to/v2-r1-release.json \
  --fixture-root /path/to/public-fixtures \
  --arm vidux_cockpit \
  --scenario-class durable_state \
  --fixture-id durable-01 \
  --replica 1
```

The packet binds both the source-manifest and fixture-release digests. It may
contain the public fixture path and oracle commitment, but never an oracle
path, evaluator receipt, or oracle body. Raw result rows must repeat both
digests and the fixture-specific commitment before scoring can begin.

## Release Limits

The release command is local-only and does not start a model, make a network
request, copy a fixture into an arm workspace, or score a result. The evaluator
or runner still owns workspace isolation, provider receipts, transcript
receipts, hidden-oracle adjudication, and the eventual raw-row publication.
