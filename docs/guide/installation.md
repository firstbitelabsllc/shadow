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

## Upgrading from the old name

Shadow was previously published as pilot-puppy. Project evidence written before
the rename lives in `.pilot-puppy/`; new evidence goes to `.shadow/` (`mv
.pilot-puppy .shadow` in a project if you want one directory). Remove the old
global install and its mounts, then re-run `bash install.sh` so
`~/.claude/skills`, `~/.agents/skills`, and `~/.cursor/skills` point at this
checkout.
