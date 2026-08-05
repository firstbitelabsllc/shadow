# Native hosts

Pilot Puppy supports `codex`, `claude-code`, and `cursor`. You may choose the
host directly, or use foreground `pilot-puppy route` to choose one declared
generic role/native-host surface before explicitly launching it. Route cannot
verify or guarantee the provider model or billing tier inside that host.

Every run requires one exact clean Git worktree, one frozen task file, one task
ID, and one or more exact allowed paths. Scope escape, missing receipt,
non-zero exit, timeout, or missing passing tests fails closed. The returned
claim stays `accepted_by_lead: false` until a person or lead agent reproduces
the proof. Pilot Puppy supplies the receipt contract to the host and records
the frozen task's SHA-256, not its prompt or provider output. If a route packet
is provided, its task hash, roster revision/hash, and host must match before
launch.

Receipt summaries and test names are bounded public text. Unknown test fields,
secret-shaped values, control characters, and absolute paths are rejected
before the attempt is written.

Pre-existing ignored files must be inside an allowed path or the bounded local
evidence directory. This keeps ignored files inside the same scope audit.
Ignored files that appear during the run—interpreter caches or dependency
installs created by the bounded proof—never block scope. They are listed in
the attempt receipt as `ignored_artifact_paths` for review; they cannot reach
a commit, a merge, or the clean lead re-proof checkout.

## Optional owner-local seat selector

Pilot Puppy normally invokes the selected native host with its existing native
defaults. If you explicitly maintain a local model/profile selector, bind it to
one declared generic roster slot:

```bash
pilot-puppy seat init
pilot-puppy seat set --slot debug-codex --profile PROFILE
pilot-puppy seat set --slot dev-cursor --model MODEL
```

Then add `--use-seat` to `pilot-puppy host run` together with `--route-file`.
The ready route identifies one exact current roster slot; Pilot Puppy validates
the private mapping against that same roster snapshot before it starts a host.
`--use-seat` cannot be used without a route, and a missing/mismatched mapping
fails before launch.

The only supported selector forms are a model for Codex, Claude Code, or Cursor
and a profile for Codex. The selector is passed as one native argv option; it is
not retained in the public attempt shape, route packet, plan, browser or status
projection, or package. Pilot Puppy does not discover selector names, inspect
provider accounts or quotas, or add fallback/retry behavior.
