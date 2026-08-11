<!-- shadow:archive:v1:m2-board-live:sha256:8a0b16386fe6d2c7f697d358dd6c2104e3633595e3f5351795097baee0a026de:cas:ce84f5115fe9381a4336f0d90bab786783b0e88c59ba84be134762fa7e04b766:head:ed976754cd461a449b56f529c9d38e4b17e77384:blob:bcd0484468f882f35ba01f58cba3ca51e19af6e3:successor:~gsrc -->
# Archived milestone: m2-board-live

Source: `PLAN.md`

## Exact milestone block

### M2 — Board live
- [completed] scanner serves gated entity/mode/milestone/checkpoint counts ~t2b8 | proof: cmd scripts/shadow-python.sh -m unittest tests.test_status_focus
- [completed] read-only board view on desktop and phone ~j6n4 | proof: cmd scripts/shadow-python.sh -m unittest tests.test_browser_shell | needs: ~t2b8
- [completed] full gate matrix green and v3.0.x released ~r9c3 (DoD) | proof: cmd npm run verify | needs: ~j6n4

- Archived milestone: [m3-v4-core](docs/plan-archive/m3-v4-core.md) <!-- shadow:lifecycle:m3-v4-core:sha256:c3de76e0f5eb235331c4a255bce55339d51c6c37a27f32bfa6a1d74d615cf1c1:cas:26447780540ee0c0526d277c322548b1b69d5da4661470c0f62f3d3cbe286a49:head:b719ea4418bb23272aeefc9d69eb50ad57efb166:blob:2e1a8c8853fc67c84b795bb56cf8caf23f728e29:successor:~disc -->

## Exact Progress receipts

- 2026-08-05T23:05:00Z ~r9c3 PROOF seat=chief out=PRs #247/#248/#249 squash-merged
  with hosted checks 11 pass / 1 skip each; releases v2.3.0
  (`6a25eb51…45e2bc`), v2.3.1 (`893e75fe…c0ffd2`), v2.3.2 (`fdc0876d…32be92`)
  public; full local matrix Python 180/180, Playwright 10/10, vitest 4/4,
  docs, privacy 0 findings.
- 2026-08-05T23:05:00Z ~r9c3 DONE seat=chief
- DOD d2 Board live, read-only, both viewports | C: ~t2b8,~j6n4 | proof: `npm run test:e2e` -> 10/10 incl. zero-write and shell-hidden assertions | status: Verified
- 2026-08-05T21:30:00Z ~m3k7 ~q8f2 ~t2b8 ~j6n4 DONE seat=chief — Method v1
  build slice from fresh `main@1ed58392`: AGENT.md, docs/reference/method.md,
  SKILL.md Method section, 4 contract tests, board scanner (3 TDD tests), and
  the read-only board view (2 e2e specs, desktop+phone). Steal-spec research
  grounded in source reads of beads (hash IDs, ready predicate), ralph
  (one-item loops, AGENT.md content law), spec-kit (analyze lint passes),
  liatrio (DoD coverage matrix), superpowers (skill enforcement), and OpenSpec
  (lesson-delta archive). Proofs on this head: contract tests 4/4, browser
  unittest 20/20, playwright 10/10, docs build, privacy scan ok. 'huncho'
  verified as plastic-labs/honcho — a Postgres+deriver second store; adopt its
  hook *pattern* only, not the store.

- 2026-08-09T00:37:00Z ~t2b8 PROOF scripts/shadow-python.sh -m unittest tests.test_status_focus -> Ran 20 tests, OK. Replaces the retired `npm run test:py`. (cmd)
- 2026-08-09T00:38:00Z ~j6n4 PROOF scripts/shadow-python.sh -m unittest tests.test_browser_shell -> Ran 7 tests, OK. Replaces `npm run test:e2e`, whose playwright board suite was deleted with npm; test_browser_shell ports its four source-contract assertions verbatim. (cmd)
