<!-- shadow:archive:v1:m4-amp-the-goal-is-a-pointer:sha256:9781a93bc559c3ffc38ebb9fbb267698835f8305560c149d02bd22fe1f3ea98b:cas:7fcd6566f792c5fc100859d7faded963e5246f85e7dfa07cce63cc24ebd0ab53:head:61840d6fdcdba5753ff03db7a5fac383ab504bcc:blob:1eef09e7ec4b6bf6c8ec1ca08c5ba2f592b25578:successor:~hrcx -->
# Archived milestone: m4-amp-the-goal-is-a-pointer

Source: `PLAN.md`

## Exact milestone block

### M4 — Amp: the goal is a pointer
- tools: goal skill, amp docs, Python
- [completed] amp emits a bounded PLAN goal ~a4mp | proof: cmd npm run test:py
- [completed] amp projects grammar tools ~t0ol | proof: cmd npm run docs:build | needs: ~a4mp
- [completed] status uses v4 Brief ~c9ut | proof: read shadow status -> v4, no v3 error | needs: ~a4mp
- [completed] specific goals name 1–4 local skills; master is skill-free, PLAN owns the roster ~gskl | proof: cmd scripts/shadow-python.sh -m unittest tests.test_grammar_contract
- [completed] tagged amp emits its installed repo goal ~s4ip (DoD) | proof: gate owner resume: installed `shadow amp` emits the repo goal | needs: ~t0ol, ~c9ut, ~gskl

## Exact Progress receipts

- 2026-08-08T20:30:00Z ~c9ut PROOF shadow status on this repo -> renders the v4 Brief (project shadow, Mode ship, milestone M4 2/4, resume ~c9ut itself — the output was its own proof), zero "outcome must be a string"; v4 plans route through the amp parser so status and amp can never disagree, legacy v3 plans keep the old view; 168 py tests OK incl 3 new status pins (schema-error regression, cwd-independence, JSON shape)
- 2026-08-07T22:55:00Z ~t0ol PROOF npm run docs:build -> "build complete in 1.78s", amp.md + grammar § Milestone law tools line rendered (run fresh in this checkout before the flip)
- 2026-08-07T22:55:00Z ~a4mp PROOF npm run test:py -> 12/12 test_amp + full py suite + lint:plan 0 blocking, all in the same commit as this flip; dogfood: `bin/shadow amp` on this plan exited 1 "no open task — mint the successor" BEFORE M4 existed (goal-chaining enforced by the tool itself) and emits M4's goal block after
- 2026-08-07T22:55:00Z STRUCT M4 added | trigger: owner directive 2026-08-07 (verbatim: "a goal prompt MUST MUST MUST be a pointer to the durable plan data source") — amp is Shadow P0; M3 closed 04:55Z handing the chain to product goals with no Shadow successor row, so this is also that missing successor. Why now: the 4k goal ceiling is hit by every real multi-project goal tonight. Contradicts: nothing — the per-milestone tooling line is pattern-not-store, consistent with the honcho ruling; `shadow status`'s v3 outcome schema DOES contradict the v4 grammar (250/250 plans report "needs a valid Brief") and is named as cut row ~c9ut rather than diluting the grammar.
- 2026-08-11T21:25:30Z ~gskl PROOF scripts/shadow-python.sh -m unittest tests.test_grammar_contract -> pass (accept)

## Receipts left in the live plan

- shared with live task(s): ~nxt1
