# Voxtral Reader Add-on — INBOX

## Open

- [2026-05-02] **Awaiting Leo's M5 audible-playback confirmation.** Phase 1 (M1-M7) is technically shipped. The only remaining gap is human ear-on-speaker verification. **30-second test:** (1) confirm `launchctl list | grep mlx-audio` shows PID + exit 0, (2) open `http://localhost:7191/` in Chrome, (3) click any plan card, (4) click the 🔊 button in the top bar, (5) listen. Expected: Voxtral reads it, chunks highlight in sequence, button returns to "🔊 Read" cleanly. Reply by editing this INBOX entry to `[verdict: <ok|broken — what happened>]` or by appending a Progress entry to `PLAN.md` directly. Once confirmed, M5 flips fully [completed] and Phase 2 (voice cloning UI, voice picker, streaming) + Phase 3 (Studio install) unblock. Autonomous evidence so far: `evidence/2026-05-02-m5-verification.md` + 4 isolated-Chromium screenshots showing chunk highlight migration; only the speaker-output stage is unverified.

## Skipped / archived

- [2026-05-01] ~~Awaiting Leo's V0 verdict on Voxtral-Realtime-WebGPU Space.~~ Obsoleted by PIVOT-3 — that Space serves Voxtral-Mini-3B (ASR), wrong direction. Phase 1 shipped with Voxtral 4B-TTS via mlx-audio instead.
