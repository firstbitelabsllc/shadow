# Small coordination recipes

Vidux supplies a plan/proof/resume contract, not a worker catalog. These
provider-neutral patterns are enough for most multi-agent work:

## Read-only research

Give the worker a question, bounded sources, and a short evidence format. The
owner checks important claims before changing the plan.

## Bounded implementation

Give the worker exact files, the expected behavior, and a verification command.
The owner reviews the diff and reruns the gate.

## Adversarial review

Give the reviewer an exact revision and explicit failure classes. Findings are
drafts until reproduced against that revision.

## Cold resume

Read the plan, revision, working tree, and named proof. Continue the active row
instead of reconstructing project state from a chat.

Keep provider setup and scheduling in the coding host.
