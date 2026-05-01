# Modal CLI install — 2026-05-01

## Install

Installed via `uv tool install modal` → `modal v1.4.2` at `/Users/leokwan/.local/bin/modal`.

## Auth state

`~/.modal.toml` does NOT exist. Auth not yet completed.

## Next step (requires Leo's browser)

Leo runs `modal token new` in his shell. The CLI:
1. Prints a URL to authenticate at modal.com
2. Opens browser automatically
3. Leo signs in / signs up with GitHub or Google
4. Token gets written to `~/.modal.toml`

Verify with `modal token info`.

## Cron-loop safety

If Leo hasn't OAuthed by the time the cron fires the next cycle, T1 stays [in_progress] with this evidence file as proof of partial progress. Cycle marks the task [blocked: awaiting Leo modal token new OAuth] only if `~/.modal.toml` is still missing two cycles later (≥1 hour stall).
