# Contributing

Shadow is MIT. Use it, fork it, bend it.

## What helps most right now

- **First-use reports.** You installed it, followed the README, and got
  confused or stuck at some step. Open an issue and say which step. That is
  the most useful thing anyone can send me today.
- **Bugs with a small example.** A fresh session lost the thread, or
  `accept` passed something it should have refused. Strip out anything
  personal and include the plan snippet and the command.
- **Small pull requests.** Typos, a doc that's wrong, a reproduction test
  for a bug you hit. Keep it to one thing and I'll review it.

## What I'll probably say no to

Larger changes to the core loop, new subcommands, and anything that makes an
external board (Linear, Jira, GitHub Projects) a second source of truth for
what's claimed or done. Each computer's local board owns coordination and the
local `PLAN.md` owns proof; round-tripping that through a cloud board is the
exact failure Shadow exists to avoid. Open an issue first if you're thinking
about something in that range, so neither of us wastes a weekend.

## Running the tests

Git, Bash, and Python 3.10+ are the whole toolchain.

```bash
scripts/shadow-python.sh -m unittest discover -s tests -p 'test_*.py'
PLAN_PATH=$(bin/shadow init --here | awk -F': ' '{print $2}')
bin/shadow lint "$PLAN_PATH"
scripts/shadow-python.sh scripts/shadow-release-package.py --allow-dirty
```

Those three are what CI runs. If you see `npm run` in an old document, it's
stale; npm was removed in August 2026.

## Style

No linter or formatter config in this repo. Match the file you're in. For
the agent-facing prose (`AGENT.md`, `SKILL.md`, `docs/reference/`): say the
mechanism, name the file, cut anything that doesn't change a decision.
