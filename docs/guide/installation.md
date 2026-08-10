# Installation

Requirements: Git, Bash, Python 3.10+, and one supported native coding host.
No Node, no npm, no package manager — the clone *is* the install, and
`git pull` is the update.

```bash
git clone https://github.com/firstbitelabsllc/shadow.git
cd shadow
bash install.sh
shadow doctor
```

`install.sh` links `bin/shadow` into `~/.local/bin` and mounts the skill in
every host root that already exists (`~/.claude/skills`, `~/.agents/skills`,
`~/.cursor/skills`). Two flags change that:

```bash
bash install.sh --bin-dir /usr/local/bin   # put the command somewhere else
bash install.sh --no-skills                # command only, skip the host mounts
```

The mount points at the same repository; it does not copy state or credentials.
The default install also writes Shadow's marker-delimited standing block into
Claude and Codex host instructions without replacing surrounding text. Cursor
uses an explicit global User Rules projection: Shadow prints the exact block
and derived hash, never invents a file path, and never claims it inspected the
application setting. A fresh uncoached Cursor chat is the final proof.
`--no-skills` deliberately skips both mounts and host-instruction installation.

## Upgrading from the old name

Shadow shipped under a different name before 0.1.0. Its compatibility path is
gone: evidence lives in `.shadow/`, and a repository still carrying the
pre-rename evidence directory shows as dirty until that directory is renamed
to `.shadow/` or deleted. Remove the old global install and its mounts, then
re-run `bash install.sh` so `~/.claude/skills`, `~/.agents/skills`, and
`~/.cursor/skills` point at this checkout.
