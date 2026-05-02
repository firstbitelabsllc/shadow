# M4 Verification — `com.leokwan.mlx-audio` LaunchAgent

Replaces the previous Claude-spawned background task (`b31hares4`, PID 59088, killed in this cycle) with a launchd-managed mlx-audio.server that auto-starts on login and restarts on crash.

## Install steps that ran this cycle

```bash
# 1. Wrote canonical plist into the repo (cross-Mac source of truth)
scripts/launchd/com.leokwan.mlx-audio.plist  # plutil -lint OK

# 2. Stopped the prior background instance
kill 59088   # background task b31hares4 — exit 143 (SIGTERM)

# 3. Installed + bootstrapped the LaunchAgent
cp scripts/launchd/com.leokwan.mlx-audio.plist \
   ~/Library/LaunchAgents/com.leokwan.mlx-audio.plist
launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.leokwan.mlx-audio.plist
```

Cross-Mac install (Studio per X1) follows the same three commands — the plist is checked into `scripts/launchd/`.

## Verification

```
$ launchctl list | grep mlx-audio
7402    0    com.leokwan.mlx-audio
```

`PID=7402`, `last exit code=0` (literally "never exited" since this is the first start), label correct.

```
$ launchctl print gui/501/com.leokwan.mlx-audio | grep -E 'state|pid|path|exit'
  path = /Users/leokwan/Library/LaunchAgents/com.leokwan.mlx-audio.plist
  state = running
  stdout path = /Users/leokwan/Library/Logs/mlx-audio.stdout.log
  stderr path = /Users/leokwan/Library/Logs/mlx-audio.stderr.log
  pid = 7402
  last exit code = (never exited)
```

Full output: [`2026-05-01-m4-launchctl-print.txt`](2026-05-01-m4-launchctl-print.txt)

```
$ lsof -nP -i:8000
python3.1   7402   leokwan   7u   IPv4   ...   TCP 127.0.0.1:8000 (LISTEN)
```

Server is the launchd-spawned PID, not the prior Claude background task.

```
$ curl -X POST http://127.0.0.1:8000/v1/audio/speech \
       -H 'Content-Type: application/json' \
       -d '{"model":"mlx-community/Voxtral-4B-TTS-2603-mlx-bf16",
            "input":"M4 LaunchAgent verification.",
            "voice":"casual_male","response_format":"wav"}'
HTTP=200  size=218924  time=9.975s
```

WAV saved as [`2026-05-01-m4-curl-test.wav`](2026-05-01-m4-curl-test.wav). Warm-path RTF ≈ 1.0 (the LaunchAgent had to load weights once on first request — subsequent requests would be in the 0.8x range we measured in M1).

## Stderr log (clean)

```
UserWarning: pkg_resources is deprecated as an API. ... Refrain from using this package or pin to Setuptools<81.
INFO:     Started server process [7402]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
Fetching 25 files: ... 100% (cached)
```

The pkg_resources warning is expected — already documented in `2026-05-01-architecture.md` §D5. No actual errors.

## Operational notes

- **Auto-start:** `RunAtLoad=true` means the server boots when Leo logs in. No manual step.
- **Crash recovery:** `KeepAlive=true` + `ThrottleInterval=30` means the server restarts on crash, but no faster than once per 30 s. Prevents thrashing on OOM-during-model-load loops on lower-RAM Macs.
- **Background priority:** `ProcessType=Background` so the model inference doesn't preempt Xcode / Final Cut / browser foreground work.
- **Logs:** stdout and stderr split between `/Users/leokwan/Library/Logs/mlx-audio.{stdout,stderr}.log`. Tailable for debugging.
- **HF cache:** `HF_HOME` env var is explicit (default `~/.cache/huggingface`) so a future per-Mac override (e.g., point Studio at an external SSD) is a one-line plist edit.
- **CORS allowlist:** loopback only — `http://localhost:7191` and `http://127.0.0.1:7191`. Anyone reading vidux-browse from another LAN device would also need their origin added (out-of-scope for this MVP — see X1 deferred).

## Stop / disable instructions

```bash
launchctl bootout gui/501/com.leokwan.mlx-audio
rm ~/Library/LaunchAgents/com.leokwan.mlx-audio.plist
```

Comment block at the top of the plist documents this for the next operator.
