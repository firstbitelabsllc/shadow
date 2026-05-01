# Higgs Reader PoC

## Purpose

Verify whether **eyes-free reading of Claude analysis on a walk** is something Leo actually wants to use — and if yes, ship a leojkwan.com `/lab/reader` page that does it. Project name retains the "higgs" prefix for git history continuity, but the **active path is Mac-native TTS** (Apple `say` / AVSpeechSynthesizer / Web Speech API). Higgs Audio V2 + Modal are deferred to Phase 4 (full-duplex voice chat) where cloud GPU is unavoidable for STT anyway.

The killer use case: hands-free consumption of agent output during walks / commutes / dog-walks. PoC question is "does the EXPERIENCE feel right?" — not "is the voice quality state-of-the-art?" Quality upgrades are reversible; conviction about the use case is the load-bearing decision.

## Evidence

- [Source: WebSearch 2026-05-01] Higgs Audio V2 = #1 trending TTS on HuggingFace. 75.7% win rate vs gpt-4o-mini-tts on EmergentTTS Emotions; Apache 2.0; CUDA-only, 24GB VRAM minimum, NO Apple Silicon path.
- [Source: WebFetch 2026-05-01] Live HF Space (`smola/higgs_audio_v2`) on ZeroGPU free tier, but anonymous queue rejects requests (verified cycle 5 — `evidence/2026-05-01-hf-space-attempt.md`).
- [Source: shell check 2026-05-01] macOS `say` CLI lists 184 voices installed by default. Samantha is the en_US default. Premium / Enhanced voices (Ava, Allison, Tom, Nicky, Zoe) are NOT installed yet — `defaults read com.apple.speech.voice.prefs` returns "domain does not exist."
- [Source: shell check 2026-05-01] AVSpeechSynthesizer (AVFoundation, available on macOS + iOS) exposes `speechSynthesizer(_:willSpeakRangeOfSpeechString:utterance:)` delegate — emits per-word boundary events natively. **No external forced-alignment needed for the Mac-native path** (whisperx becomes unnecessary).
- [Source: shell check 2026-05-01] Web Speech API (`SpeechSynthesisUtterance` + `boundary` event) gives the same primitive in browsers — Safari iOS/macOS uses the same Apple voices.
- [Source: observed] Leo (2026-05-01): "I want to just have a proof of concept to verify whether Higgs can do the job properly."
- [Source: observed] Leo (2026-05-01): "is there a goood reason to pay when we can do this on local?"
- [Source: observed] Leo (2026-05-01): "fucks sake /auto didn'd u steer it ur my assistant" — flagged that I should have pushed back when "I'm sold on Higgs" was incompatible with Apple Silicon. Pivot triggered cycle 10.
- [Source: observed] Leo (2026-05-01): long-term plan = "speak to vidux while remote... talk to AI on the go" (Hermes/EVI-style full-duplex). Phase 4. Modal account at `firstbitelabs` workspace stays set up for that future.

## Constraints

- ALWAYS: Phase 0 PoC tests the **experience**, not the **voice quality ceiling**. Ship the lowest-cost test first.
- ALWAYS: Mac-native TTS for Phase 0 + Phase 1. No GPU spend until Phase 4.
- ALWAYS: Phase 1 reader uses `AVSpeechSynthesizer` (native) or `SpeechSynthesisUtterance` (browser) — both expose word boundary events natively, killing the whisperx requirement.
- NEVER: Create a new repo. Per global CLAUDE.md "No new repos until September 2026" — Phase 1 lives inside `leojkwan` repo at `/lab/reader`.
- NEVER: Ship a Modal-dependent Phase 1 (cloud TTS for a walking-reader is overengineered for what AVSpeechSynthesizer does free + on-device).
- NEVER: Re-enter the Higgs path unless ALL Mac-native voices fail Leo's quality bar AND voice expressiveness is verified to be the actual bottleneck (not just "I want better").

## Tasks

### Phase 0 — Mac-native PoC (active)

- [completed] M1: Generate `say` Samantha baseline sample. Saved to `evidence/2026-05-01-mac-say-samantha.aiff` (561KB) and `.m4a` (57KB, AAC). 12 sec audio. Text covers analytical content ("Higgs Audio Two beats GPT four-o on emotional expressiveness, but right now we are testing whether the eyes-free reading experience itself is worth doing"). [Evidence: evidence/2026-05-01-mac-say-samantha.m4a]
- [pending] M2: Leo listens to the Samantha sample and writes a one-line verdict to `evidence/2026-05-01-experience-verdict.md`. Verdict is one of: **GO-WITH-SAMANTHA** (default voice clears the bar — ship Phase 1 immediately), **NEED-PREMIUM** (experience clicks but voice quality is too plain — install Apple Premium voices first), **NEED-CHATTERBOX** (Apple voices won't suffice — pivot to local Chatterbox MLX), **NO-GO** (eyes-free reading isn't a use case Leo wants — kill project, archive plan). [Depends: Leo's ears. ETA: 0.1h]
- [blocked] M3: [conditional on M2 = NEED-PREMIUM] Install Apple Premium / Enhanced voices via System Settings → Accessibility → Spoken Content → System Voice → Customize → download (Ava + Allison + Tom). Verify with `say -v Ava "test"`. Generate one premium-voice sample matching M1's text for direct A/B. [Blocker: M2 verdict]
- [blocked] M4: [conditional on M2 or M3 = GO] Final verdict locks: write `evidence/2026-05-01-verdict.md`, update Decision Log, unblock Phase 1. [Blocker: M2 or M3 GO]

### Phase 1 — leojkwan.com /lab/reader (BLOCKED until Phase 0 = GO)

- [blocked] P1-T1: Add `/lab/reader` route to `leojkwan` Next.js. Textarea → "Read" button → audio player below with word-highlight + tap-to-seek. **Browser-native TTS via Web Speech API** (`SpeechSynthesisUtterance`). Word highlight via `boundary` event. Zero backend, zero GPU, zero Modal. [Blocker: Phase 0 verdict]
- [blocked] P1-T2: Word-highlight + tap-to-seek component. On `boundary` event, advance highlight; on word click, `utterance.cancel()` + restart from clicked word's start char index using `text.slice(charIndex)`. [Blocker: Phase 0 verdict]
- [blocked] P1-T3: Deploy to Vercel. Live URL = quality proof. [Blocker: Phase 0 verdict]

### Phase 2 — Vidux integration (BLOCKED)

- [blocked] P2-T1: Add 🔊 button to vidux-browse artifact pages (`~/Development/vidux/browser/`). Click → POST artifact text to leojkwan reader → opens reader with that content. [Blocker: Phase 1 ships]

### Phase 3 — iOS reader (DEFERRED)

- [blocked] P3-T1: SwiftUI app using `AVSpeechSynthesizer` directly (no Modal call). Tappable word grid + lock-screen controls + background audio playback. Word boundaries from `speechSynthesizer(_:willSpeakRangeOfSpeechString:utterance:)` delegate. [Blocker: Phase 2 ships]

### Phase 4 — Full-duplex voice chat (LONG-TERM, this is where Modal returns)

- [blocked] P4-T1: Full voice loop = STT (Modal-hosted Whisper / Parakeet) + VAD (silero-vad on-device) + Claude API + TTS (AVSpeechSynthesizer first; upgrade to Higgs Audio V2 on Modal only if voice expressiveness is the bottleneck). Sub-300ms latency target. [Blocker: Phase 3 ships AND multi-week budget approved]

### Higgs / Modal path — DEFERRED (artifacts retained for Phase 4)

- [blocked: deferred per pivot] T1: Modal CLI install + OAuth (was [completed] cycle 9; auth still valid at `~/.modal.toml`, workspace `firstbitelabs`). Useful for Phase 4 STT. No GPU spent.
- [blocked: deferred per pivot] T2: `modal_app/higgs.py` (was [completed] cycle 2 + extended cycle 9 with whisperx). 202 lines, py_compile OK. Stays in repo as Phase 4 reference.
- [blocked: deferred per pivot] T3: Modal deploy (never ran — killed cycle 9 before image build completed).
- [blocked: deferred per pivot] T4: whisperx forced-alignment integration (code drafted cycle 9 but unnecessary for Mac-native path — AVSpeechSynthesizer's word-range delegate replaces it).
- [blocked: deferred per pivot] T5, T6: Higgs-specific quality samples + verdict. Replaced by M1-M4 Mac-native equivalents.

## Decision Log

- [DIRECTION] [2026-05-01] Modal as inference backend, not local. ~~Reason: Higgs requires CUDA + 24GB VRAM. Apple Silicon path doesn't exist.~~ **REVERSED [PIVOT 2026-05-01 cycle 10] — see PIVOT entry below.**
- [DIRECTION] [2026-05-01] PoC scope is QUALITY VERIFICATION ONLY. No UI. No persistence. No auth. **Refined [PIVOT cycle 10]: PoC tests the EXPERIENCE (does eyes-free reading feel good?), not voice quality ceiling.**
- [DIRECTION] [2026-05-01] Phase 1 lives in `leojkwan` repo at `/lab/reader` route. **Still valid post-pivot.**
- [DIRECTION] [2026-05-01] Whisperx for forced alignment, not Higgs-native timestamps. ~~Reason: Higgs is an acoustic-token LLM and doesn't emit per-word timing.~~ **REVERSED [PIVOT cycle 10] — Mac-native path uses AVSpeechSynthesizer's `willSpeakRangeOfSpeechString` delegate which emits per-word events natively. Whisperx unnecessary.**
- [DIRECTION] [2026-05-01] T2 dep on T1 dropped, T3 takes the dep instead. **Moot post-pivot; T1-T4 all deferred.**
- [PIVOT] [2026-05-01 cycle 10] Cloud Higgs → Mac-native TTS. **Trigger:** Leo's pushback "is there a goood reason to pay when we can do this on local?" + "fucks sake /auto didn'd u steer it ur my assistant." **Reason:** I should have steered when Leo said "I'm sold on Higgs" — the PoC question (does eyes-free reading feel good?) is answerable in 30s with `say` for $0, not 10 cycles of Modal infra. Higgs/Modal artifacts retained for Phase 4 (full-duplex voice chat) where STT cloud GPU is unavoidable. **How to apply:** all Phase 0+1 work uses Mac-native APIs only. Cloud paths require explicit Phase 4 unblock (multi-week budget approval). [Evidence: evidence/2026-05-01-pivot-to-local.md]
- [DELETION] [2026-05-01 cycle 10] whisperx integration (cycle 9 work product) deleted from active scope. Reason: AVSpeechSynthesizer / Web Speech API emit per-word boundary events natively. Forced alignment of known text is a problem we don't have on the Mac-native path. Code stays in `modal_app/higgs.py` as Phase 4 reference; do NOT re-add to Phase 0/1.

## Progress

- [2026-05-01] Plan created. Modal CLI not installed (T1 will install + auth). PoC scope locked to Phase 0 only. Cron loop starting at 30-min cadence to advance the plan over the next ~2 hours. Next: T1 (Modal setup).
- [2026-05-01] Cycle 1: Modal CLI installed (v1.4.2 via uv tool). Auth blocked on Leo's browser OAuth — `modal token new` must be his hands. T1 flipped to [in_progress]. Cron job 477bdef0 firing :07/:37 — next cycle will check `~/.modal.toml` and flip T1 to [completed] if found, else hold and proceed once Leo OAuths. Next: Leo runs `! modal token new` in shell.
- [2026-05-01] Cycle 2: Leo's OAuth still pending (`~/.modal.toml` absent). Re-evaluated dep graph — T2 (write Modal app file) doesn't actually need auth, only T3 (deploy) does. Reordered: dropped [Depends: T1] from T2, added it to T3 alongside existing T2 dep. Wrote `modal_app/higgs.py` (105 lines) — A100 image from nvidia/pytorch:25.02-py3, clones higgs-audio repo and pip-installs editable, web endpoint at `generate`, local entrypoint `smoke_test`. py_compile OK. T2 [completed]. Next: T3 still blocked on T1 OAuth — when Leo runs `modal token new`, next cycle ships T1 + T3 in sequence.
- [2026-05-01] Cycles 3-4: Both idle on T1. `~/.modal.toml` still absent through 4 total cycles. T1 flipped [in_progress] → [blocked].
- [2026-05-01] Cycle 5: Leo invoked /pilot /vidux /auto "keep driving." Tested HF Space (`smola/higgs_audio_v2`) as parallel-track quality verification path. ZeroGPU anonymous queue rejected 3 attempts. Conclusion: HF Space is also gated on Leo's OAuth.
- [2026-05-01] Cycles 6-8: Three consecutive no-op cycles. Modal + HF both still unauthed.
- [2026-05-01] Cycle 9: Pivoted from no-op to forward progress. Wrote T4 whisperx integration into `modal_app/higgs.py` ahead of T3 deploy. Image now pip-installs `whisperx`; @modal.enter() loads alignment model alongside Higgs. py_compile OK. T4 flipped [pending] → [in_progress]. Then Leo OAuthed (`modal token new` succeeded, workspace `firstbitelabs`). T1 flipped [completed]. `modal deploy` started in background.
- [2026-05-01] Cycle 10 — **PIVOT**: Leo pushback ("good reason to pay when we can do this on local?" + "/auto didn't u steer it"). Killed background `modal deploy` (exit 144). Generated Mac-native baseline via `say -v Samantha -o evidence/2026-05-01-mac-say-samantha.aiff "..."` — 561KB aiff + 57KB m4a, 12 sec. Plan rewrites: Phase 0 replaced T1-T6 (Higgs path) with M1-M4 (Mac-native). Phase 1 reader rewritten to use Web Speech API / AVSpeechSynthesizer — no Modal, no whisperx (per-word boundary events are native to both APIs). Higgs/Modal artifacts retained for Phase 4 (full-duplex voice chat). Modal account at `firstbitelabs` stays set up for Phase 4 STT. **Cron 477bdef0 should be deleted** — its cycle prompt is calibrated for the Higgs path (T1-T6 instructions) and is wrong-shape post-pivot. Next: Leo listens to `evidence/2026-05-01-mac-say-samantha.m4a` → writes M2 verdict.
