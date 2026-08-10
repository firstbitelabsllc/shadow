# Security Policy

Report vulnerabilities through GitHub private vulnerability reporting for
`firstbitelabsllc/shadow`. Do not include credentials or private project
content in a public issue. We aim to acknowledge reports within five business
days.

## Security boundary

- The browser binds only to loopback, serves allowlisted static files, and
  reads regular non-symlink `PLAN.md` files reached through the computer board.
  It exposes no write endpoint.
- Browser responses and local receipts exclude prompts, transcripts,
  credentials, provider payloads, and absolute private paths.
- Root-board claim and checkpoint transactions use a same-computer advisory
  lock plus atomic replacement; readers see the complete old or new board.
- Native-host work requires a clean exact Git worktree, a frozen task file, an
  explicit path allowlist, a timeout, and one closed receipt. Any scope escape
  or missing proof fails closed.
- Shadow does not relay credentials, choose a cloud provider, expose a
  non-loopback service, run a daemon, or keep a second queue.

The repository's privacy scan, secret scan, focused security regressions, and
fresh packed install must pass before release.

## Supported versions

Only the latest `0.1.x` release and current `main` receive security fixes.
