# Installation

Requirements: Git, Bash, Python 3.10+, and one supported native coding host.

```bash
git clone https://github.com/firstbitelabsllc/pilot-puppy.git
cd pilot-puppy
npm install -g .
pilot-puppy doctor
```

Optional skill mounts:

```bash
ln -sfn "$(pwd)" "$HOME/.claude/skills/pilot-puppy"
ln -sfn "$(pwd)" "$HOME/.codex/skills/pilot-puppy"
ln -sfn "$(pwd)" "$HOME/.cursor/skills/pilot-puppy"
```

The mount points at the same repository; it does not copy state or credentials.
