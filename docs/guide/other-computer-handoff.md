# Other-computer handoff

This is the portable starting point for Shadow on another Mac.

## Bootstrap

```bash
git clone --branch shadow-v1.0.1 --depth 1 \
  https://github.com/firstbitelabsllc/shadow.git
cd shadow
bash install.sh
shadow doctor
```

`install.sh` links the command and mounts the same skill in each native host
root that exists (`~/.claude/skills`, `~/.agents/skills`, `~/.cursor/skills`).
Pass `--no-skills` to link the command alone.

Expected result: `shadow doctor` reports product identity, command, and the
host/mount checks that exist on that computer. Missing optional hosts or mounts
are warnings; Cursor cold directive activation is an explicit unsupported
surface. Authentication stays inside the native host on that computer.

## The normal loop

1. Establish one stable seat name and run `shadow status --by <seat>`. The
   computer board owns global project priority, entity pointers, claims,
   owners, leases, and entity resume checkpoints.
2. Resume that seat's claims, then read the selected entity's committed
   `PLAN.md`, which owns its milestones, checkpoints, detail, and proof.
3. Atomically claim and dispatch path-disjoint checkpoints through supported
   native hosts. Freeze each handoff and allow only the exact paths it may change.
4. Review the diff and reproduce the important test locally. A host receipt is
   evidence, not acceptance by itself.
5. Record each result, uncertainty, proof, blocked wake, and reachable successor
   in the owning `PLAN.md`; continue until full acceptance or hard rails.

Do not create another queue, autonomous router, daemon, watcher, cloud
executor, credential relay, transcript store, or parallel status database. A
foreground, explicit role choice may be used locally, but it never launches or
substitutes a host. Keep evidence inside the project-local
`.shadow/evidence/` path and never put credentials, prompts, raw
transcripts, provider payloads, or absolute private paths in it.

## Main skill map

| Surface | Use it for |
| --- | --- |
| `/shadow` | Start/resume work, read the Outcome, drain reachable lanes, and leave proof plus successors. |

`shadow amp` is a CLI subcommand, not a mounted skill: it projects a
paste-ready resume block for a checkpoint the seat already claimed — see
[amp](../reference/amp.md). Two optional extensions fill routed recall
(`memory`) and finish-quality-plus-voice (`taste`) when mounted — see
[extensions](../reference/slots.md). The pre-mortem extension is gone: its
pre-commit timing has no shipped mechanism (a repo may declare an
adversarial-lens slug — post-work review, a different moment — or a person
may delegate foresight to their own method). Diagrams stay Brief-contract
law, no slot involved.

Use native Codex, Claude Code, or Cursor for execution. Provider-specific
helpers are adapters; none becomes the plan authority or stores credentials.

## Read the public state

- Repository: `firstbitelabsllc/shadow`
- Do not trust a version or commit copied into this guide. Read the protected
  `main` branch and release tags before starting work.
- Use `git ls-remote origin refs/heads/main refs/tags/shadow-v*`, then read
  `VERSION`
  from the exact checkout or release tag you chose.
- Run `shadow doctor` on that checkout. The result describes that
  computer's mounts and host tools; it is not a remote-host claim.

## Fast local readback

```bash
git fetch origin main --tags
git merge --ff-only origin/main
git status --short --branch
shadow doctor
```

When handing work to the next computer, pass the repository, exact revision,
entity plan pointer, claimed checkpoints, allowed paths, proof commands, and
blocked wakes. That is enough context; do not paste a transcript or copy the
other computer's root board.
