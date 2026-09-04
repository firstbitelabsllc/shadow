# Minimum-sufficient Shadow without proof loss

Status: **APPROVED — direction approved 2026-09-01; written contract confirmed by Leo 2026-09-03.**
Baseline: fresh `origin/main@6345e52c73058feb9911ca53d08cfcbbd130fc16`; no product source changed yet.

## Decision

> Preserve the full requested outcome with the minimum sufficient implementation.
> Reuse or delete before adding a concept, compatibility path, test, or agent lane; add one only to prevent a named current failure.

This positive selection rule enters the existing static goal. It does not shrink queue drain, safe fanout, acceptance, release-train, telemetry, or distinct source/merge/install/live-proof contracts.

## Evidence and boundary

The [first post](https://x.com/aibuilderclub_/status/2093695923801210893) contributes explicit goals, non-goals, acceptance, untouched areas, reuse, and a stop to speculative plan growth. The [second](https://x.com/hqmank/status/2094773109505311029) points to [Ponytail](https://github.com/DietrichGebert/ponytail).

Ponytail's [primary agentic benchmark](https://github.com/DietrichGebert/ponytail/blob/main/benchmarks/results/2026-06-18-agentic.md) reports 54% less aggregate feature LOC across twelve tasks, one model, and four runs per cell; savings range from near zero on irreducible CRUD to 94% where native HTML replaces custom UI. Its safety tier was 100% for baseline/Ponytail and 95% for a bare one-line prompt. Four of 192 LOC cells timed out, and feature cells were not run through server/browser completeness proof. The repository also records higher cost on some reasoning-model tasks. These are useful results, not a Shadow quota.

Shadow borrows only the ladder: understand the full outcome, reuse, prefer standard/native capability, use an installed dependency, then add the smallest mechanism. No Ponytail hook, runtime, benchmark, dependency, provider assumption, or numeric target enters Shadow. Acceptance is whole-branch net-negative LOC with every named Shadow invariant still proved.

## Measured baseline and ownership

`scripts/shadow-python.sh -m unittest tests.test_all_boats_law tests.test_standing_goal tests.test_release_train tests.test_verification_tiers tests.test_observed_gauntlet tests.test_observed_routing_gauntlet`

Result: `Ran 89 tests in 17.120s` and `OK`; expected connection, auth, missing-event, and accepted-without-readback errors appeared only in fail-closed falsifiers.

The first complete pre-change run executed 1,312 tests in 1,301.895s and exposed 13 failures in `tests.test_shadow_host`: its shared fake host claimed success without consuming the frozen stdin task, so the runner correctly reported `host stdin failed`. Clean `origin/main` reproduced that result in 60/60 trials; adding only `sys.stdin.read()` to the existing fake made all 38 host tests green. This is a baseline fixture prerequisite, not a reason to weaken product delivery.

- `docs/reference/host-integration.md` is the one static-goal source; `tests/test_standing_goal.py` proves its clauses.
- `tests/test_amp.py` already owns executable queue drain, path-disjoint fanout, and full acceptance.
- `docs/reference/method.md` already owns Thermo/Ponytail as review lenses; `AGENT.md` already prefers reuse/deletion.
- `tests/test_all_boats_law.py` duplicates those assertions and scans unrelated tracked prose, but also owns one earned test-discovery guard.

## Exact source delta

- Fold the two-sentence invariant into the existing `Capabilities:` paragraph in `docs/reference/host-integration.md`; add its exact clauses to `GoalVerb.test_it_carries_every_load_bearing_clause` in `tests/test_standing_goal.py`.
- Delete `tests/test_all_boats_law.py`: its banned-phrase scanner proves vocabulary, not outcome; its goal/amp assertions have existing owners.
- Move `NoTestFileHidesTestsBehindAMidFileGuard`, unchanged in behavior, to semantic owner `tests/test_release_train.py`.
- In `scripts/shadow-ci.py`, replace `tests.test_all_boats_law` with `tests.test_release_train` in `BASELINE`, remove it from `DOC_MODULES`, and add no alias or replacement scanner.
- In `tests/test_shadow_host.py`, make the existing shared fake consume stdin before emitting its receipt; add no product branch, helper, retry, or new test.

Expected source files are exactly the five modified files above plus the deletion. Unless another named proof fails, leave method/agent prose, amp, telemetry/Langfuse code, grammar, board, lifecycle, installer, schemas, CLI, dependencies, config, hooks, prompts, seats, and test framework untouched.

## Acceptance

| Layer | Check | Required result |
|---|---|---|
| Focused | Baseline command above, minus the deleted module and plus `tests.test_telemetry` | Exit 0; count reduction maps only to deleted duplicates |
| CI ownership | `tests.test_verification_tiers tests.test_release_train` | Deleted module absent; discovery guard remains baseline |
| Host fixture | `scripts/shadow-python.sh -m unittest tests.test_shadow_host` | Frozen stdin is consumed; all 38 tests green; product safeguard unchanged |
| Full source | `scripts/shadow-python.sh scripts/shadow-ci.py run --run-all true --modules-json '[]'` | Exit 0; no declared proof silently skipped |
| Adversarial train | `scripts/shadow-python.sh scripts/shadow-ci.py gauntlet --scratch-root <fresh-temp-dir>` | Exit 0 in disposable root |
| Package | `scripts/shadow-python.sh -m unittest tests.test_release_package` | Exit 0 at pinned source SHA |
| Langfuse contract | observed-gauntlet, observed-routing, and telemetry modules | Fake delivery plus exact readback green; missing readback red; owner opt-in preserved |
| Live Langfuse | `scripts/dev/shadow-observed-gauntlet.py --rounds 1 --jobs full-discover` with explicit loopback `SHADOW_LANGFUSE_*` | One trace written and independently read back by exact trace ID |
| Size | `git diff --numstat origin/main...HEAD` across the whole branch, including this spec | Deleted lines exceed added lines |

Do not run the unrelated provider matrix to manufacture Langfuse proof. If the owner-local listener or explicit credentials are absent, record that exact wake; checked-in fake E2E still must pass and never substitutes for live proof. Source-tested, merged, installed, and cold dogfood receipts remain separate.

## Falsifiers and rollback

- Goal extraction, doctor, or installed copy drifts; release-train baseline becomes impractically broad; queue drain/fanout disappears; accepted-but-unreadable Langfuse turns green; or size falls by removing discovery, privacy, error handling, or proof-stage separation: reject the change.
- Rollback is a normal source revert. There is no state migration, schema, config, dependency, install side effect, compatibility surface, or new authority to unwind.

## Gate

Leo confirmed this exact file boundary, whole-branch negative-LOC gate, retained proof matrix, and live exact-ID readback on 2026-09-03. Material expansion needs a new ruling rather than silent plan growth.
