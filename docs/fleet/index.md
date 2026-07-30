# Host integrations

Vidux works without a fleet. It does not install, schedule, authenticate, or
restart coding agents.

If your coding host can run multiple workers, keep the same small contract:
each worker reads the repository plan, owns a bounded surface, verifies its
result, and leaves proof plus a cold-resume next move.

- [Platform boundary](platforms.md) — what Vidux can expect from a host.
- [Host-owned execution](operations.md) — safe coordination without a second
  scheduler.
- [Harness authoring](harness.md) — a short prompt that points back to repo
  authority.

The host-specific pages are boundary notes, not setup or lifecycle promises.
Follow the host's current official documentation for scheduling and runtime
configuration.
