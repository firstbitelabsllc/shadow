# Quick start

Shadow has one loop: create or read a project plan, claim a checkpoint on this
computer, do only that claimed work, then leave proof or a precise wake.

## 1. Create or open the plan

From a Git project with no `PLAN.md` yet:

```bash
shadow init --here
$EDITOR PLAN.md
shadow lint PLAN.md
```

Fill the generated Brief, then add a task whose proof is executable in this
checkout. For example:

```text
- [pending] document a verifiable change ~ab12 | proof: cmd python3 -m unittest discover -s tests
```

Use the repository's real test command and replace the illustrative row text;
`npm test` is not a Shadow default.
Existing plans should be read and edited in place rather than initialized over.

## 2. Read the computer board and claim one row

Choose a stable seat name and read from any directory:

```bash
shadow status --by your-seat
```

Copy the exact `shadow throw` command printed for a reachable row. Quote ids
such as `~ab12` in zsh:

```bash
shadow throw --repo . --task '~ab12' --by your-seat
shadow amp --repo . --by your-seat
```

The root board at `~/.shadow` owns the claim and lease. The project `PLAN.md`
still owns the row text, proof, and evidence; the board never copies them.

## 3. Work through a bounded host

Use the returned packet yourself, or run a sealed host only over the exact
claimed paths:

```bash
shadow host run \
  --host codex \
  --repo "$PWD" \
  --task-file /tmp/task.md \
  --task-id focused-fix \
  --allowed-path src/fix.py \
  --allowed-path tests/test_shadow_init.py \
  --out .shadow/evidence/focused-fix.json
```

Review the diff and reproduce the proof locally. A host receipt is evidence,
not acceptance by itself.

## 4. Close the loop

For a passing `cmd` proof, use the only flip path:

```bash
shadow accept --repo . --row '~ab12' --by your-seat
```

For a person-observed `read` or `gate` proof, append the result to the plan and
return the claim. For blocked work, append one Deferred wake naming the exact
condition before returning it:

```bash
shadow return --repo . --row '~ab12' --by your-seat
shadow status --in-flight --json
```

At the end of the chat, render an **Ongoing tasks** footer from that fresh
in-flight projection: claims first, then the current seat's reachable and
waiting rows, with owner, state, proof, and wake. Print `Active tasks: none`
only when the board has no ongoing work. This is a view of `~/.shadow`, never a
second queue.

## Next references

- [Commands](../reference/commands.md) for every flag and exit boundary.
- [Host integration](../reference/host-integration.md) for cold-start behavior.
- [Other-computer handoff](other-computer-handoff.md) for a fresh machine.
