# Other-computer handoff

This is the portable starting point for Pilot Puppy on another Mac. Pilot
Puppy is the one chief-of-staff surface for coding work: it reads the owning
repository's `PLAN.md`, explains the Outcome and current proof, offers the next
decision, and drives one bounded task through native Codex, Claude Code, or
Cursor.

## Bootstrap

```bash
git clone https://github.com/firstbitelabsllc/pilot-puppy.git
cd pilot-puppy
npm install -g .
pilot-puppy doctor
```

Mount the same skill in each native host you use:

```bash
ln -sfn "$(pwd)" "$HOME/.claude/skills/pilot-puppy"
ln -sfn "$(pwd)" "$HOME/.agents/skills/pilot-puppy"
ln -sfn "$(pwd)" "$HOME/.cursor/skills/pilot-puppy"
```

Expected result: `pilot-puppy doctor` reports the product identity, command,
three host probes, and each installed mount as passing. Authentication stays
inside the native host on that computer.

## The normal loop

1. In the target project, read `PLAN.md` before acting. It is the only Outcome,
   proof, and resume authority.
2. Inspect the exact revision and worktree state, then resume the in-progress
   row or take the highest unblocked row.
3. Make one bounded change through one selected native host. Freeze the task in
   a file and allow only the exact paths it may change.
4. Review the diff and reproduce the important test locally. A host receipt is
   evidence, not acceptance by itself.
5. Record the result, uncertainty, proof, and one next A/B/C decision in the
   owning `PLAN.md`.

Do not create another queue, router, daemon, watcher, cloud executor,
credential relay, transcript store, or parallel status database. Keep evidence
inside the project-local `.pilot-puppy/evidence/` path and never put credentials,
prompts, raw transcripts, provider payloads, or absolute private paths in it.

## Main skill map

| Skill | Use it for |
| --- | --- |
| `/pilot-puppy` | Start/resume work, read the Outcome, drive one bounded host task, and leave proof plus a resume point. |
| `/amp` | Turn a vague request into one short, repository-grounded prompt. It does not dispatch or own a queue. |
| `/ponytail` | Decide what to delete, reuse, defer, or implement before adding scope. |
| `/thermo` | Review the working implementation after correctness for ownership, duplication, and boundary failures. |
| `/browse` | Research current external facts or projects; keep sources and uncertainty explicit. |
| `/local` | Inspect local files, commands, and runtime state without assuming chat context is current. |
| `/skillbox` | Mount or validate skills on this computer and confirm the resolved source path. |
| `/github` | Read or change remote PR, check, release, and branch state when the task requires it. |
| `/slop` | Remove duplicated or generated instructions when the handoff or plan becomes noisy. |

Use native Codex, Claude Code, or Cursor for execution. Provider-specific
helpers are adapters; none becomes the plan authority or stores credentials.

## Current public state

- Repository: `firstbitelabsllc/pilot-puppy`
- Release: `v2.0.0`
- Current `main`: `0c6d8ce1` (documentation closeout is ahead of the shipped tag)
- Shipped release commit: `6375c84a`
- Release package SHA-256: `9827381f6570dac1bf5e66611fae4056e18f3a14c6a914d85a099e5d5643b8cb`
- Local gate: `pilot-puppy doctor` is 11/11 green; the public, package, docs,
  browser, privacy, and hosted checks are green.

The remaining resume item is the same sealed native Codex task after the
account quota reset. Re-run that exact task, require `status: ok`, require only
its allowed-path change, and reproduce the proof from the lead checkout. Do
not weaken the gate or substitute a version probe for execution proof.

## Fast local readback

```bash
git fetch origin main --tags
git merge --ff-only origin/main
git status --short --branch
pilot-puppy doctor
```

When handing work to the next computer, pass the repository, exact revision,
owning `PLAN.md` row, allowed paths, proof command, and one resume predicate.
That is enough context; do not paste a transcript.
