# Installation

Requirements: Git, Bash, Python 3.10+, and one supported native coding host.
No Node, no npm, no package manager — the stable release clone *is* the install.

```bash
git clone --branch shadow-v1.0.0 --depth 1 \
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
`~/.cursor/skills`). Two flags change that:

```bash
bash install.sh --bin-dir /usr/local/bin   # put the command somewhere else
bash install.sh --no-skills                # command only, skip the host mounts
```

The mount points at the same repository; it does not copy state or credentials.
The default install also writes Shadow's marker-delimited standing block into
Claude and Codex host instructions without replacing surrounding text. Cold
Cursor directive activation is unsupported because Cursor exposes no
equivalent reviewed writable file. The installer does not invent a path or ask
you to paste into an unverified setting; Cursor's skill mount and sealed host
runner remain supported.
`--no-skills` deliberately skips both mounts and host-instruction installation.

## Upgrading from the old name

Shadow shipped under a different name before 0.1.0. Its compatibility path is
gone: evidence lives in `.shadow/`, and a repository still carrying the
pre-rename evidence directory shows as dirty until that directory is renamed
to `.shadow/` or deleted. Remove the old global install and its mounts, then
re-run `bash install.sh` so `~/.claude/skills`, `~/.agents/skills`, and
`~/.cursor/skills` point at this checkout.
