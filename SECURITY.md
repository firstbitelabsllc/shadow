# Security Policy

Report vulnerabilities through GitHub private vulnerability reporting for
`firstbitelabsllc/shadow`. Do not include credentials or private project
content in a public issue. We aim to acknowledge reports within five business
days.

## Security boundary

- The browser binds only to loopback, serves three allowlisted static files,
  reads regular non-symlink `PLAN.md` files under its selected root, and accepts
  one same-origin A/B/C endpoint.
- Browser responses and local receipts exclude prompts, transcripts,
  credentials, provider payloads, and absolute private paths.
- Local decision and checkpoint receipts use exclusive atomic creation inside
  the selected Git project. Repeating the same decision is idempotent.
- Native-host work requires a clean exact Git worktree, a frozen task file, an
  explicit path allowlist, a timeout, and one closed receipt. Any scope escape
  or missing proof fails closed.
- Shadow does not relay credentials, choose a cloud provider, expose a
  non-loopback service, run a daemon, or keep a second queue.

The repository's privacy scan, secret scan, focused security regressions, and
fresh packed install must pass before release.

## Supported versions

Only the latest `2.x` release and current `main` receive security fixes.
