# Commands

| Command | Purpose |
|---|---|
| `pilot-puppy init --here` | Create `PLAN.md` without overwriting one. |
| `pilot-puppy status --root PATH` | Read current plan rows. |
| `pilot-puppy browse --root PATH` | Start the loopback briefing UI. |
| `pilot-puppy checkpoint … --proof TEXT` | Update one exact row and atomically write one receipt. |
| `pilot-puppy roster init\|show\|prefer` | Create, show, or locally prioritize a declared generic work-role slot. |
| `pilot-puppy route …` | Explain one explicit generic role/native-host choice without launching it. |
| `pilot-puppy host probe --host HOST` | Check a native host without using it. |
| `pilot-puppy host run …` | Run one sealed task in one clean worktree. |
| `pilot-puppy doctor` | Check installation, skill mounts, and native hosts. |

Run `pilot-puppy help <command>` for exact flags.

The roster command is local setup/display only. `route` selects only a declared
generic role and native-host surface, then prints the choice and stops. Neither
command selects a provider/model, starts a coding host, dispatches work, or
creates a queue. See [foreground routing](routing.md).
