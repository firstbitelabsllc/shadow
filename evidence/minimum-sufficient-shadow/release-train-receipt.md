# Shadow minimum-sufficient release-train receipt

Owning checkpoint: `~ms42`
Repository: Shadow
Source branch: `codex/minimum-sufficient-shadow-20260903`
Source commit under test: `b777ac3e5865840bdc9c458a2f5ad85c351f127f`
Receipt scope: source-tested release-train evidence only. This receipt does
not claim merge, installation, deployment, live dogfood, or customer outcome.

## Result

The deterministic root release-train proof completed with exit code 0. Its
recorded stages were:

- story E2E pass 1: 1 test, 21.330 seconds, OK;
- story E2E pass 2: 1 test, 17.677 seconds, OK;
- migration/lifecycle: 198 tests, 462.675 seconds, OK;
- adversarial/crash: 179 tests, 627.168 seconds, OK;
- capability/rotation: 174 tests, 83.887 seconds, OK;
- rollback/upgrade: 146 tests, 172.825 seconds, OK; and
- release package/install: exit 0.

The package/install receipt was:

```text
shadow release package: OK (1.3.0, 122 files, sha256=207c4654185d8c9ef5c3682735fc2501ad5aee44fd5305f8d7f9674967f76006)
```

Independent full discovery used the exact command below and exited 0:

```text
scripts/shadow-python.sh scripts/shadow-ci.py run --run-all true --modules-json '[]'
```

Observed result: `Ran 1353 tests in 2054.831s; OK (skipped=2)`.
The two skipped tests are retained as an explicit limitation of this receipt;
they are not counted as passing evidence and are not silently reclassified.

The focused source/proof batch used this command and its test process exited 0:

```text
scripts/shadow-python.sh -m unittest tests.test_standing_goal tests.test_release_train tests.test_verification_tiers tests.test_shadow_host tests.test_observed_gauntlet tests.test_observed_routing_gauntlet tests.test_telemetry
```

Observed result: `138 tests in 34.424s, OK`.
The surrounding zsh wrapper later exited 1 only because it assigned the
reserved shell variable `status`; that wrapper failure is not a test failure.

The targeted gallery-related batch also exited 0:

```text
scripts/shadow-python.sh -m unittest tests.test_secret_scan_workflow tests.test_python_resolution tests.test_install_doctor tests.test_gallery_visual
```

Observed result: `25 tests in 19.862s, OK (skipped=1)`. The one skip is the
gallery visual case because Playwright is absent unless `SHADOW_VISUAL=1` is
set. It is not counted as passing visual evidence.

## Non-receipt diagnostic

A later `LiveTwoSeatProof` diagnosis was intentionally interrupted after
repeated `host_timeout`/`host_failed` skips and individual failure/error
signals under host load. It is not a passing receipt, was not used to qualify
`~ms42`, and does not establish two-seat or host-liveness proof. No claim is
made for the unresolved full-discovery skips beyond the explicit counts above.

## Verification

At receipt creation, `git diff --check` was clean and the source commit was
verified as the exact SHA recorded above. Only this receipt file is included
in the receipt commit; the pre-existing untracked implementation plan and all
other working-tree state are intentionally preserved.
