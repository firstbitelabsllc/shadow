# Security Policy

## Reporting a vulnerability

If you discover a security issue in vidux, please report it responsibly:

1. **Do not open a public GitHub issue.** Security issues should be reported privately.
2. Use GitHub private vulnerability reporting for `firstbitelabsllc/vidux` when available.
3. Include: what you found, steps to reproduce, and potential impact.
4. You'll receive an acknowledgment per the [Response SLA](#response-sla) below.

## Response SLA

We aim to acknowledge security reports within 5 business days. Critical issues
will be addressed as quickly as possible; non-critical fixes follow the next
release cycle.

## Scope

Vidux is an orchestration tool that reads and writes markdown files. It does not:
- Handle authentication or user credentials
- Run a web server or accept network connections
- Store or transmit sensitive data

The primary security surface is:
- **Automation prompts** — lane prompts in `~/.claude-automations/` that drive agent behavior
- **Git operations** — scripts that commit, push, and create PRs
- **Shell scripts** — `scripts/` directory executed by agents

## What We Watch For

- Scripts that could execute arbitrary code from untrusted plan files
- Git operations that could overwrite or delete user data
- Prompt injection vectors in plan/evidence files that could alter agent behavior
- Credential leakage in git history (audited clean as of 2026-05-13)

## Supported versions

Only the latest supported version line receives security fixes.

| Version          | Status              |
| ---------------- | ------------------- |
| `2.23.x`         | supported           |
| Older commits    | unsupported         |
