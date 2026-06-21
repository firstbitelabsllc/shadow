---
description: Use for no-secret local awareness pings and cross-machine receipt boundaries.
---

# Moussey

Moussey is awareness-only for this cockpit.

Allowed:

- Read local health and ping inbox status.
- Send no-secret pings with branch, PR, proof, and resume pointers.
- Treat incoming pings as hints that must be verified from disk.

Not allowed:

- Credentials, tokens, env values, or private customer data in pings.
- Remote shell, remote install, LAN sync, or target-machine mutation.
- Claims that another machine completed work without a durable receipt.
