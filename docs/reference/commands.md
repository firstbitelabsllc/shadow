# Commands

| Command | Purpose |
|---|---|
| `pilot-puppy init --here` | Create `PLAN.md` without overwriting one. |
| `pilot-puppy status --root PATH` | Read current plan rows. |
| `pilot-puppy browse --root PATH` | Start the loopback briefing UI. |
| `pilot-puppy checkpoint … --proof TEXT` | Update one exact row and atomically write one receipt. |
| `pilot-puppy roster init\|show\|prefer` | Create, show, or locally prioritize a declared generic work-role slot. |
| `pilot-puppy seat init\|show\|set` | Configure one owner-local model/profile selector for an existing native slot. |
| `pilot-puppy route …` | Explain one explicit generic role/native-host choice without launching it. |
| `pilot-puppy host probe --host HOST` | Check a native host without using it. |
| `pilot-puppy host run …` | Run one sealed task in one clean worktree. |
| `pilot-puppy doctor` | Check installation, skill mounts, and native hosts. |

Run `pilot-puppy help <command>` for exact flags.

The roster command is local setup/display only. `route` selects only a declared
generic role and native-host surface, then prints the choice and stops. The
optional `seat` command is a separate owner-local overlay: it can attach one
safe native model selector to an already-declared slot, or a Codex profile to a
Codex slot. It never changes a route and takes effect only with `host run
--use-seat` plus a ready sealed route. These commands do not discover providers,
accounts, quota, prices, or models; start a host automatically; dispatch work;
or create a queue. See [foreground routing](routing.md) and
[native hosts](native-hosts.md).
