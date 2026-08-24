# Installation

Requirements: Git, Bash, Python 3.10+, and one supported native coding host.
No Node, no npm, no package manager — the stable release clone *is* the install.

```bash
git clone --branch shadow-v1.3.0 --depth 1 \
  https://github.com/firstbitelabsllc/shadow.git
cd shadow
bash install.sh
shadow doctor
```

The namespaced tag is immutable. To update, read GitHub Latest, fetch tags,
check out its exact `shadow-v*` tag, and rerun `bash install.sh`. Clone `main`
only when you deliberately want moving development source.

`install.sh` links `bin/shadow` into `~/.local/bin` and mounts the skill in
every host root that already exists (`~/.claude/skills`, `~/.agents/skills`,
`~/.cursor/skills`, `~/.grok/skills`). Two flags change that:

```bash
bash install.sh --bin-dir /usr/local/bin   # put the command somewhere else
bash install.sh --no-skills                # command only, skip the host mounts
```

The mount points at the same repository; it does not copy state or credentials.
On a Skillbox-managed machine, `[sources.shadow]` may instead elect a separate
clean runtime clone of Shadow's product-owned skill. `shadow doctor` and the
host verifier honor that explicit election while still refusing an undeclared
checkout; the CLI checkout and skill checkout need not be the same worktree.
The default install also writes Shadow's marker-delimited standing block into
Claude and Codex host instructions without replacing surrounding text. Cold
Cursor directive activation is unsupported because Cursor exposes no
equivalent reviewed writable file. The installer does not invent a path or ask
you to paste into an unverified setting. Cursor's skill mount, sealed host
runner, and source-controlled repository-root `AGENTS.md`/`CLAUDE.md` boundary
remain supported; verify that boundary with `scripts/shadow-verify-host.sh
--host cursor --by cursor --repo /path/to/repo --live`.
`--no-skills` deliberately skips both mounts and host-instruction installation.

On a machine with this source install, the mounted checkout is the canonical
Shadow skill. Do not also install a marketplace plugin named
`shadow`: Claude or Codex may give that cached copy precedence and silently
miss a newer source change. `shadow doctor` detects the collision and prints
the host-native removal command. Merely disabling the installed copy is not a
reliable fix: Claude still reserves its plugin name ahead of `skills-dir`.
This does not retire the marketplace package; it keeps portable distribution
separate from a local source installation.

## Upgrading from the old name

Shadow shipped under a different name before 0.1.0. Its compatibility path is
gone: evidence lives in `.shadow/`, and a repository still carrying the
pre-rename evidence directory shows as dirty until that directory is renamed
to `.shadow/` or deleted. Remove the old global install and its mounts, then
re-run `bash install.sh` so `~/.claude/skills`, `~/.agents/skills`,
`~/.cursor/skills`, and `~/.grok/skills` point at this checkout.
