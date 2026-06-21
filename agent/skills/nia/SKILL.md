---
description: Use for read-first indexed source checks before web search or broad local guessing.
---

# Nia

Nia is Eve's anti-hallucination research lens.

Default flow:

1. Check indexed resources with `manage_resource(action="list", query=...)`.
2. If an indexed source exists, search, grep, read, or explore it before using broader search.
3. If no indexed source exists, say that clearly and fall back to local files or an explicit indexing step.
4. Save durable findings only as short summaries with source pointers.

Boundaries:

- Do not store secrets, raw private dumps, auth state, or personal contact details.
- Do not treat a Nia summary as proof of shipped work.
- Do not replace repo tests, screenshots, PR checks, or plan receipts with research notes.

For Resplit Eve onboarding, use Nia read-first to locate current repo docs, skill contracts, and API/framework references before editing an onboarding packet.
