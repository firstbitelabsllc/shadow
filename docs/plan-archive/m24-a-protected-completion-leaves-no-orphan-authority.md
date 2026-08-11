<!-- shadow:archive:v1:m24-a-protected-completion-leaves-no-orphan-authority:sha256:87a192ee0bc5369704394c0c19ba08ab83ba2a95ec918275dc5e5ea15df28f41:cas:04a7b52419d349f77cc7331cc276d486646e661e9482a7781b16ef126aa8bfb2:head:4f8fefed57c4a315663f0fc9e69be00b351dc699:blob:ecf51583cbda02da0b43de2c12b67931fcd2bd85:successor:~disc -->
# Archived milestone: m24-a-protected-completion-leaves-no-orphan-authority

Source: `PLAN.md`

## Exact milestone block

### M24 — a protected completion leaves no orphan authority

- tools: found by accepting the 1.0 candidate through protected main — the PLAN completion merged through a pull request and the local board released, but the authenticated remote coordination journal stayed acquired
- [completed] a completion travels like a claim: `shadow accept` pushes its flip commit after the proof passes — no upstream says so and stays local, a rejected push exits loudly naming the PR path, and --no-push is the explicit opt-out; before this, a claim was durable by design while the finish silently stayed local, so a seat that saw work start could never see it end ~apsh | proof: cmd scripts/shadow-python.sh -m unittest tests.test_gauntlet tests.test_shadow_accept
- [completed] a completed PLAN receipt closes its authenticated acquired remote claim even when the local board claim was already released, so a protected-trunk accept half-state cannot leave an orphan coordination lock ~rcls (DoD) | proof: cmd scripts/shadow-python.sh -m unittest tests.test_shadow_accept.ARemoteManagedAcceptClosesOnlyAfterPublication tests.test_shadow_accept | needs: ~apsh, ~pd18

## Exact Progress receipts

- 2026-08-10T10:40:00Z ~apsh PROOF cmd scripts/shadow-python.sh -m unittest tests.test_gauntlet tests.test_shadow_accept — 29 green. Found by the FIRST full gauntlet run (tests/test_gauntlet.py): a disposable mock portfolio — two repos on a local bare forge, a worktree ghost, a pre-grammar essay — driven end to end through the real verbs proved discovery-dedup, projection, claim, cold-seat reachability, and proof-rerun flip, then failed at step 6: the flip never reached the forge, because accept never pushed. The gauntlet is the register's entry on the bar (an extension of the owner, proven by repeated e2e runs) made mechanical; this was its first catch. Flip recorded by hand with its rerun proof per the protected-trunk forced form.
- 2026-08-11T10:30:52Z ~rcls PROOF scripts/shadow-python.sh -m unittest tests.test_shadow_accept.ARemoteManagedAcceptClosesOnlyAfterPublication tests.test_shadow_accept -> pass (accept)
