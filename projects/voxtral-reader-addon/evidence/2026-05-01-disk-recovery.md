# Disk Recovery — 2026-05-01

## Incident

First mlx-audio smoke test (`bjjvivzeq`) failed with `RuntimeError: Data processing error: File reconstruction error: IO Error: No space left on device (os error 28)`. Voxtral 4B-TTS download (~8GB) blew through remaining disk space.

## State at failure

```
Filesystem      Size    Used   Avail Capacity
/dev/disk3s5   926Gi   902Gi   307Mi   100%
```

Top consumers:
- `~/Library/Developer/Xcode/DerivedData` — 72 GB (Resplit / iOS build artifacts, regenerable)
- `~/Library/Containers/com.docker.docker` — 55 GB
- `~/Library/Caches` — 7.2 GB
- `~/.cache/huggingface` — 6.3 GB (partial Voxtral download)

## Recovery actions (this cycle)

1. Removed partial Voxtral download: `rm -rf ~/.cache/huggingface/hub/models--mlx-community--Voxtral-4B-TTS-2603-mlx-bf16` → recovered 6 GB.
2. Nuked Xcode DerivedData: `rm -rf ~/Library/Developer/Xcode/DerivedData/*` → recovered ~64 GB. Safe per `/disk-clean` skill: DerivedData regenerates on next Xcode build.
3. Skipped: iOS DeviceSupport (0B already), CoreSimulator/Devices (14 GB but Simulator was actively running — PIDs 801, 1373, 2147, 3207, 5032 — Resplit dev work in progress).

## State after recovery

```
Filesystem      Size    Used   Avail Capacity
/dev/disk3s5   926Gi   832Gi    70Gi    93%
```

70 GB free, comfortable buffer for the 8 GB Voxtral download + 16+ GB working RAM Voxtral inference will use.

## Process fix (avoid this next time)

- Pre-flight check: before ANY large model download (>1 GB), assert `df -h ~ | awk 'NR==2 {gsub("Gi","",$4); exit ($4 < 20)}'` (≥20 GB free required). Wire into mlx-audio smoke-test script if we ever script the install for cross-machine.
- Cron consideration: a periodic `du -sh ~/Library/Developer/Xcode/DerivedData ~/.cache/huggingface ~/Library/Containers/com.docker.docker | tee ~/.agent-ledger/disk-watch.log` weekly could catch this earlier. Out-of-scope for this plan, surface as separate `/disk-clean-cron` if Leo wants.

## Re-run

Smoke test re-fired after recovery as background task `bsg299x4q` (2026-05-01 23:0X). Same args. Expected 5-15 min for fresh 8 GB download + synthesis.
