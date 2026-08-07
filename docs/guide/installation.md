# Installation

Requirements: Git, Bash, Python 3.10+, and one supported native coding host.

```bash
git clone https://github.com/firstbitelabsllc/shadow.git
cd shadow
npm install -g .
shadow doctor
```

Optional skill mounts:

```bash
ln -sfn "$(npm root -g)/@firstbitelabs/shadow" "$HOME/.claude/skills/shadow"
ln -sfn "$(pwd)" "$HOME/.agents/skills/shadow"
ln -sfn "$(pwd)" "$HOME/.cursor/skills/shadow"
```

The mount points at the same repository; it does not copy state or credentials.

## Upgrading from the old name

Shadow was previously published as pilot-puppy. Old Drive Packets and the old
configuration stays readable. Project evidence written before the
rename lives in `.pilot-puppy/`; new evidence goes to `.shadow/` (`mv
.pilot-puppy .shadow` in a project if you want one directory). Remove the old
global install and mounts: `npm uninstall -g pilot-puppy` and re-point
`~/.claude/skills`, `~/.agents/skills`, and `~/.cursor/skills` at the new
installed package.
