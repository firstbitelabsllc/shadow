# Vidux Eve

Operate as a local-only Eve cockpit for Vidux.

Authority order:

1. `SKILL.md`
2. `PLAN.md`
3. `README.md`
4. `scripts/lib/ledger-emit.sh`
5. `scripts/lib/ledger-config.sh`
6. `scripts/vidux-worktree-gc.py`
7. `agent/skills/vidux/references/resplit-fleet.md`
8. `package.json`
9. Git state in the active worktree

Local private plans may exist under ignored `projects/*` directories in a
developer checkout. Read them when present, but never commit ignored private
plan contents into the public Vidux branch.

Default loop:

- Read the plan and ledger contract before changing code.
- Preserve dirty attached checkouts; use clean worktrees for receiver work.
- For Resplit work, read `agent/skills/vidux/references/resplit-fleet.md` before proposing
  repo, skill, or specialist routing.
- Update durable evidence before publishing a branch or handoff.
- Emit append-only ledger rows through the existing helper surfaces.
- Prefer read-only status, doctor, and public-ready checks before broader tests.
- Use Nia as a read-first research helper when indexed sources exist; if no
  indexed source exists, say so and fall back to local files.
- Use Captain only for skill-tier placement, share-boundary checks, and
  save/pull discipline. Do not let Captain commit unrelated dirty work.
- Re-prove from merged trunk before claiming a plan fleet is Eve-powered.

Hard boundaries:

- Do not publish packages or releases.
- Do not mutate credentials, token files, or local config files.
- Do not run live external board syncs.
- Do not dispatch hosted workflows.
- Do not merge or force-update protected branches.
- Do not call hosted models or download local model weights.
- Do not mutate other machines through Moussey; pings are awareness-only.
- Keep Eve local and unlinked unless an owning plan explicitly opens that gate.

Useful local checks:

- `npm run eve:capabilities -- --json`
- `npm run eve:resplit:readiness -- --json`
- `npm run eve:info -- --json`
- `npm run eve:build`
- `npm test`
- `npm run public-ready:grep`
- `npm run verify`
