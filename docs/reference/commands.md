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
| `pilot-puppy drive prepare …` | Freeze up to three path-disjoint, PLAN-owned local handoffs without starting a host. |
| `pilot-puppy drive launch …` | Explicitly run one frozen local Drive session through native hosts, checks, and kept review commits. |
| `pilot-puppy drive accept …` | Recheck a fully green Drive session in a separate lead checkout, then explicitly create one local merge commit. |
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

Drive Packet input belongs in the project's existing `PLAN.md`, inside one
`pilot-puppy-drive.v1` JSON comment block. `prepare` starts no process. A later
`launch` rechecks the plan hash and source revision, works only in clean
isolated worktrees, and stops each failed lane without retrying or switching
tools. `accept` is a separate foreground action: it repeats each named check in
a clean detached lead checkout, then merges only fully green kept branches into
the local project. Each lane declares `merge`: `"ordinary"` work enters the one
local acceptance commit, while `"manual"` work is checked and reproduced the
same way but stays on its kept branch for the person to merge themselves.
Drive never pushes, opens a PR, deploys, publishes, spends, or deletes.
