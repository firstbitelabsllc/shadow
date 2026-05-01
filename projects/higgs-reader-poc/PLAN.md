# Higgs Reader PoC

## Purpose
Verify whether Higgs Audio V2 (BosonAI, Apache 2.0) produces good-enough audio for Leo's "read me Claude analysis on a walk" use case. **This is a quality-gate PoC, not a product build.** Stop after the verdict — only proceed to Phase 1 (leojkwan.com `/lab/reader` UI) if the PoC clears the bar.

The killer use case is eyes-free consumption of agent output during walks / commutes / dog-walks. The endgame is full-duplex voice chat with vidux (Hermes / EVI-style), but that's a multi-week project — this PoC is the load-bearing first step. If Higgs sounds bad, the whole vision is dead.

## Evidence
- [Source: WebSearch 2026-05-01] Higgs Audio V2 = #1 trending TTS on HuggingFace. 75.7% win rate vs gpt-4o-mini-tts on EmergentTTS Emotions; 30.4% for ElevenLabs Multilingual v2. WER 1.78 / Emotion-Sim 86.13 on ESD.
- [Source: WebFetch 2026-05-01] Apache 2.0 license, 24GB VRAM minimum, CUDA-only, no Apple Silicon path. Model: `bosonai/higgs-audio-v2-generation-3B-base`.
- [Source: WebFetch 2026-05-01] Boson blog confirms zero-shot multi-speaker dialogue, automatic prosody, voice cloning, 24kHz output, melodic humming, simultaneous speech+music — without any post-training.
- [Source: WebFetch 2026-05-01] Live HF Space exists (`smola/higgs_audio_v2`) on ZeroGPU free tier. Quality preview before Modal commit.
- [Source: shell check 2026-05-01] `modal` CLI NOT installed on this machine. `~/.modal.toml` absent. Modal account auth required as T1.
- [Source: shell check 2026-05-01] `~/Development/vidux/projects/` exists with 17 active projects. `vidux.config.json` confirms `plan_store.mode=local`, this plan lives at the canonical path.
- [Source: observed] Leo (2026-05-01): "I want to just have a proof of concept to verify whether Higgs can do the job properly."
- [Source: observed] Leo (2026-05-01): "Long-term plan, if I'm gonna do it during a walk, I wanna be able to speak to vidux while I'm remote... be able to chat and like talk to an AI while I'm on the go. But that's not for now."

## Constraints
- ALWAYS: Run inference on Modal (CUDA A100/H100). No local Apple Silicon path exists for Higgs.
- ALWAYS: Output BOTH a `.wav`/`.mp3` AND a word-timestamp JSON (forced-aligned via whisperx) — tap-to-continue depends on per-word timing.
- ALWAYS: Keep PoC scope locked to quality verification. No UI. No auth. No persistence.
- NEVER: Create a new repo. Per global CLAUDE.md "No new repos until September 2026" — Phase 1 lives inside `leojkwan` repo when we get there.
- NEVER: Push to `main` of any repo. Phase 1+ ships via PR.
- NEVER: Burn cycles on Phase 1+ until Phase 0 returns a GO verdict. PoC FIRST, product SECOND.
- NEVER: Commit Modal API tokens or any secret to git. Tokens go in `~/.modal.toml` (Modal CLI default) or `.env.local` (gitignored).

## Tasks

### Phase 0 — Quality PoC (active)

- [pending] T0: Read PLAN.md + INBOX.md. Resume any [in_progress] task. If none, claim T1 and proceed. [ETA: 0.1h]
- [in_progress] T1: Install Modal CLI + OAuth. Install done via `uv tool install modal` → v1.4.2 at `/Users/leokwan/.local/bin/modal`. Awaiting Leo to run `modal token new` (browser OAuth — must be Leo's hands). Verify with `modal token info`. [Evidence: evidence/2026-05-01-modal-install.md] [ETA: 0.25h]
- [completed] T2: Write Modal app `modal_app/higgs.py` that loads `bosonai/higgs-audio-v2-generation-3B-base` + `bosonai/higgs-audio-v2-tokenizer` on an A100 GPU image. Endpoint accepts `{text: str, voice_ref: Optional[str]}` and returns `{audio_b64, duration_s, sample_rate}`. Cache weights in a Modal Volume so cold starts only pay download once. App lives at `modal_app/higgs.py`. Image built from `nvcr.io/nvidia/pytorch:25.02-py3` per Boson's recommendation, clones higgs-audio repo and pip-installs editable. Smoke-test entrypoint writes wav to `evidence/`. [Evidence: modal_app/higgs.py — py_compile OK; API surface verified against github.com/boson-ai/higgs-audio README quickstart on 2026-05-01]
- [pending] T3: Deploy with `modal deploy modal_app/higgs.py`. Smoke test via `modal run modal_app/higgs.py::smoke_test` (writes wav to evidence/) and via HTTP `curl -X POST <web-url> -d '{"text": "..."}'`. Log cold-start time + warm-start time + GPU-seconds cost to `evidence/2026-05-01-smoke-test.md`. [ETA: 0.5h] [Depends: T1, T2]
- [pending] T4: Add whisperx forced-alignment to the same Modal endpoint. After Higgs generates wav, run whisperx (wav2vec2 alignment, English) on the same GPU instance. Return `{audio_url, words: [{w, t0, t1}], duration_s}`. Test on the smoke wav from T3 — every word should round-trip with start/end timestamps. [Evidence: github.com/m-bain/whisperX] [ETA: 0.75h] [Depends: T3]
- [pending] T5: Generate 3 quality samples covering the PoC's real use cases. Save each as `evidence/2026-05-01-sample-N.{wav,json}` plus a one-line description in `evidence/2026-05-01-samples.md`. [ETA: 0.5h] [Depends: T4]
  1. **Analytical** — paste a real recent Claude analysis output (~300 words, multi-clause, technical). Tests prosody on dense reasoning text.
  2. **Creative** — a Snowcubes blog draft excerpt (~250 words, warm tone). Tests Nicole-voice texture (note: not voice-cloned yet, just default voice).
  3. **Dialogue** — a 3-speaker exchange tagged `[Leo] / [Claude] / [Vidux]`. Tests zero-shot multi-speaker — the Twitter-going-around feature.
- [pending] T6: Quality verdict. Listen to all 3 samples. Write `evidence/2026-05-01-verdict.md` with one of: **GO** (clears the bar — cleared for Phase 1), **NO-GO** (kill project — log why, archive plan, consider Chatterbox/NeuTTS), or **PIVOT** (model is good but PoC needs adjustment — e.g. needs voice cloning before verdict). Update Decision Log with the verdict. [ETA: 0.25h] [Depends: T5]

### Phase 1 — leojkwan.com /lab/reader (BLOCKED until Phase 0 = GO)

- [blocked] P1-T1: Spin up `/lab/reader` route on `leojkwan` Next.js. Textarea → "Read" button → audio player below with word-highlight + tap-to-seek. Calls Modal endpoint from T4. [Blocker: Phase 0 verdict pending]
- [blocked] P1-T2: Word-highlight player component. Binary-search current word by `audio.currentTime`. Tap any word → `audio.currentTime = word.t0`. [Blocker: Phase 0 verdict pending]
- [blocked] P1-T3: Deploy to Vercel. Verify Modal endpoint reachable from Vercel function. Live URL = quality proof. [Blocker: Phase 0 verdict pending]

### Phase 2 — Vidux integration (BLOCKED)

- [blocked] P2-T1: Add 🔊 button to vidux-browse artifact pages (`~/Development/vidux/browser/`). Click → POST artifact text/markdown to leojkwan reader → opens reader with that content. [Blocker: Phase 1 ships]

### Phase 3 — iOS reader (DEFERRED)

- [blocked] P3-T1: SwiftUI app calling same Modal endpoint. AVAudioPlayer + tappable word grid + lock-screen controls + background audio. [Blocker: Phase 2 ships]

### Phase 4 — Full-duplex voice chat (LONG-TERM)

- [blocked] P4-T1: Full voice loop = STT (Whisper / Parakeet) + VAD (turn detection) + Claude API + Higgs TTS. Sub-300ms latency target. [Blocker: Phase 3 ships AND multi-week budget approved]

## Decision Log
- [DIRECTION] [2026-05-01] Modal as inference backend, not local. Reason: Higgs requires CUDA + 24GB VRAM. Apple Silicon path doesn't exist. Re-evaluate ONLY if a high-quality Apple-native open-source TTS appears (e.g. NeuTTS-Air-MLX, Chatterbox-MLX) — and only if Phase 1+ ROI justifies the swap.
- [DIRECTION] [2026-05-01] PoC scope is QUALITY VERIFICATION ONLY. No UI. No persistence. No auth. Reason: if Higgs doesn't sound right, every downstream phase is wasted. Quality gate first; product second.
- [DIRECTION] [2026-05-01] Phase 1 lives in `leojkwan` repo at `/lab/reader` route. Reason: per global CLAUDE.md "No new repos until September 2026," and leojkwan.com is Leo's personal-tools surface — brand fit, no domain mismatch.
- [DIRECTION] [2026-05-01] Whisperx for forced alignment, not Higgs-native timestamps. Reason: Higgs is an acoustic-token LLM and doesn't emit per-word timing. Whisperx (wav2vec2-based) is real-time on the same GPU and battle-tested for word-level timestamps.
- [DIRECTION] [2026-05-01] T2 dep on T1 dropped, T3 takes the dep instead. Reason: writing the Modal app file (T2) is pure local code authoring — doesn't need Modal auth. Only deploy/run (T3) needs the OAuth'd token. Splitting the dep lets the cron loop ship T2 in parallel with Leo's OAuth step instead of stalling.

## Progress
- [2026-05-01] Plan created. Modal CLI not installed (T1 will install + auth). PoC scope locked to Phase 0 only. Cron loop starting at 30-min cadence to advance the plan over the next ~2 hours. Next: T1 (Modal setup).
- [2026-05-01] Cycle 1: Modal CLI installed (v1.4.2 via uv tool). Auth blocked on Leo's browser OAuth — `modal token new` must be his hands. T1 flipped to [in_progress]. Cron job 477bdef0 firing :07/:37 — next cycle will check `~/.modal.toml` and flip T1 to [completed] if found, else hold and proceed once Leo OAuths. Next: Leo runs `! modal token new` in shell.
- [2026-05-01] Cycle 2: Leo's OAuth still pending (`~/.modal.toml` absent). Re-evaluated dep graph — T2 (write Modal app file) doesn't actually need auth, only T3 (deploy) does. Reordered: dropped [Depends: T1] from T2, added it to T3 alongside existing T2 dep. Wrote `modal_app/higgs.py` (105 lines) — A100 image from nvidia/pytorch:25.02-py3, clones higgs-audio repo and pip-installs editable, web endpoint at `generate`, local entrypoint `smoke_test`. py_compile OK. T2 [completed]. Next: T3 still blocked on T1 OAuth — when Leo runs `modal token new`, next cycle ships T1 + T3 in sequence.
