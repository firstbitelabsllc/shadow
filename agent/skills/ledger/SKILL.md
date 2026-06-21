---
description: Use for append-only ledger rows, publish packet fields, and health checks.
---

# Ledger

Use existing ledger helper scripts instead of ad hoc JSON writes.

Expected publish packet fields:

- summary
- task id
- plan path
- proof
- handoff status
- touched files
- claimed files
- next-agent resume point

Never put secrets, tokens, personal contact details, or credential paths into
ledger rows. Prefer scoped rows tied to a repo, lane, and plan path.
