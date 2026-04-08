---
name: vidux-version
description: Report the current Vidux version, git hash, and sync status across machines.
---

# /vidux-version

Quick version and sync status check. Does not modify any files.

## Steps

1. Read `VERSION` from the Vidux repo root.
2. Run `bash scripts/vidux-install.sh version` to get the full report.
3. If the sync status shows "BEHIND origin," suggest running `vidux-install.sh upgrade`.
4. If the sync status shows "AHEAD of origin," suggest pushing: `git push`.

## Output Format

```
Vidux 2.1.0
Commit: abc1234
Sync:   up-to-date
Repo:   /path/to/vidux
Host:   macbook-pro
```

## Hard Rules

- Read only. Do not modify any files.
- Keep it to 5-6 lines of output.
- If the VERSION file is missing, say so and suggest running `vidux-install.sh install`.
