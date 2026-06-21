# Artifact Self-Improvement

> Authority Store for the cross-skill artifact self-improvement loop. The living
> operating prompt lives at `prompts/artifact-self-improvement.prompt.md`.

## Purpose

Make every artifact-producing agent cycle leave the system easier for the next
human or agent to use. "Artifact" means code, tests, docs, reports, prompt
files, plans, PR bodies, screenshots, browser HTML, dashboards, design specs,
runbooks, or any other durable output someone can open later.

## Evidence

- [Source: user 2026-06-17] Leo asked for a loop where `/goal` points to a
  dynamic prompt and work is "drive by improving" across all artifacts, not only
  code.
- [Source: user 2026-06-17] Leo clarified that 2.0/readiness loops must use
  inference to start from the true P0 UX/core workflow bugs across platforms;
  fixing P0s often collapses downstream P2/P3 polish and proof debt.
- [Source: amp SKILL.md] Prompt File Mode already defines the PLAN +
  `prompts/*.prompt.md` + compact `/goal` launcher shape.
- [Source: auto SKILL.md] Existing autonomy rules say self-improvement must be
  bounded and shared-skill evolution must stay reusable.
- [Source: vidux SKILL.md] Existing self-extend brake and publish ledger rules
  require skill changes to name the invariant, verification, sync/commit
  expectation, and stop condition before editing.
- [Source: local/slop/ledger SKILL.md patches 2026-06-17] The generic artifact
  invariant is now split across the cache, slop, and receipt surfaces.

## Constraints

- ALWAYS keep shared `/ai` guidance project-agnostic.
- ALWAYS keep Leo-private decision defaults in `/ai-leo`.
- ALWAYS keep queue/state in this PLAN first; mutate the prompt only for
  standing instruction changes.
- ALWAYS make one bounded self-improvement move or record why none exists.
- ALWAYS select true P0/core workflow rows before lower-priority polish in
  launch, readiness, and product-quality loops.
- ONLY run P2/P3 work when it directly unblocks or proves a P0, no unblocked
  P0 exists, or the current authority PLAN explicitly promotes it.
- NEVER cache secrets, raw private payloads, auth state, or current PR/deploy
  status as reusable fact memory.
- NEVER turn self-improvement into endless skill prose.

## Tasks

- [in_progress] ASI-1: Ship the baseline artifact-self-improvement invariant and P0-first loop selector across the owning skills. [Evidence: user 2026-06-17, amp/auto/local/slop/ledger SKILL.md]
- [pending] ASI-2: Add a lightweight audit script that samples skill files and checks whether artifact-producing skills name a receipt/self-improvement outcome without forcing every skill to duplicate the full rule. [Evidence: skill-creator progressive disclosure, vidux self-improvement brake]
- [pending] ASI-3: Forward-test the prompt on one non-code artifact lane and one code artifact lane, then record whether the dynamic prompt causes useful reuse or extra ceremony. [Evidence: skill-creator forward-testing guidance]
- [pending] ASI-4: Decide whether the invariant belongs in core vidux `SKILL.md` after the current dirty Vidux branch is reconciled; until then, this PLAN/prompt is the portable contract. [Evidence: vidux checkout dirty/ahead on 2026-06-17]

## Decision Log

- [DIRECTION] 2026-06-17 Use a dynamic prompt file rather than a giant `/goal` body. Reason: Amp Prompt File Mode keeps runtime state in PLAN.md and standing instruction in a prompt file.
- [DIRECTION] 2026-06-17 Treat artifact self-improvement as cross-artifact, not code-only. Reason: Leo explicitly corrected the theme to "anything and everything not just code."
- [DIRECTION] 2026-06-17 Make launch/readiness/product loops severity-first. Reason: Leo clarified that true P0 UX/core workflow bugs should outrank easy P2/P3 polish across platforms.
- [DIRECTION] 2026-06-17 Do not edit the dirty local Vidux `SKILL.md` in this pass. Reason: the main checkout is ahead/dirty with unrelated local work; this branch ships a clean PLAN/prompt packet plus skill patches in `/ai` and `/ai-leo`.

## Progress

- [2026-06-17] Created the authority store and prompt packet. Patched `/local`, `/slop`, `/auto`, `/amp`, and `/ledger` with the baseline artifact invariant plus the `/amp` P0-first loop selector.
- [2026-06-17] Opened PRs: `/ai` #65, `/ai-leo` #25, and `vidux` #146. Proof: `/ai` local tests passed, `/ai-leo` ledger audit passed, Vidux `PYTHONPATH=./browser npm test` passed 469 tests with 1 skipped, and Vidux `gitleaks detect --no-git --source . --config .gitleaks.toml --redact --verbose` found no leaks. Hosted Vidux CI is unstable before assigning runners; ASI-1 remains in progress until the PRs are merged to main.
