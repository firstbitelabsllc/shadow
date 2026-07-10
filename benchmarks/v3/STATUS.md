# Benchmark v3 Status

`vidux-cockpit-v3` is retired and non-runnable.

The frozen manifest and implementation remain inspectable as a negative
artifact. They are useful for reproducing the provider-matched schedule,
budget, journal, and deterministic-decision design, but they cannot authorize
an evaluator release, provider spend, adjudication, or product claim.

Four concrete defects require outcome-determining rule changes: opaque digest
references are accepted without resolving their bytes, synthetic evaluator
rows can produce a claim-eligible win, retry usage is omitted from decision
statistics, and a crash-torn journal cannot recover. `STATUS.json` records the
full disposition and replacement requirements.

The replacement is `vidux-cockpit-v4`. It starts as a non-runnable integrity
preflight. No evaluator release, provider run, pilot result, or verified
net-win class exists. Vidux superiority remains unproven.
