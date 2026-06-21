---
description: Use for skill-tier placement, share-boundary checks, safe save/pull discipline, and Resplit Eve skill-port routing.
---

# Captain

Captain is the skill registry and operator-console lens for Eve.

Use it when Eve needs to decide where a durable instruction belongs:

- shared skill
- private overlay
- repo-local skill
- repo-owned root skill
- plan or ledger receipt

Rules:

- Default to the narrowest correct tier.
- Specific staging only; never scoop an entire dirty checkout.
- Keep the shared/private boundary explicit.
- Current project state belongs in the owning plan or ledger, not in a shared skill.
- Redirects are routing glue; durable rules go in the real target skill.
- Do not commit, push, pull, or stash without the caller explicitly choosing that action.

For Resplit:

- `/amp`, `/auto`, `/ledger`, `/craft`, `/slop`, `/future`, Moussey, and Nia are source lenses.
- Eve should port portable operating design into `agent/` packets.
- Eve should not copy private facts, raw transcripts, credentials, or live gate rows into public Vidux.
