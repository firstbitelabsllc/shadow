# Pivot: Cloud Higgs → Mac-local TTS — 2026-05-01

## What changed

After 9 cycles of building the Modal/Higgs Audio V2 pipeline (T1 install, T2 Modal app, T4 whisperx integration drafted), Leo pushed back: *"is there a goood reason to pay when we can do this on local?"* and *"fucks sake /auto didn'd u steer it ur my assistant"*.

He's right. The PoC question — *"does eyes-free reading of Claude analysis on a walk feel good?"* — is answerable in 30 seconds with macOS's built-in `say`. I locked into Higgs because Leo said "I'm sold on Higgs" earlier in the conversation, and didn't push back when the Apple-Silicon-incompatibility constraint should have made me re-question the model choice for the PoC.

## What I should have steered

When Leo said "I'm sold on Higgs," the right response was:

> Higgs is CUDA-only. For the question you're actually asking — does the eyes-free reader EXPERIENCE feel right? — let's verify with a free local TTS first. If the experience clicks, we upgrade to Higgs only if the local quality bar fails. The model choice is reversible; the conviction about whether to build a reader at all is the load-bearing decision.

Per /auto, this was an "Audience Avoidance" trap — building infrastructure (Modal, image builds, whisperx) instead of testing the actual experience.

## The real local landscape (Apple Silicon, free)

Sorted by setup cost:

1. **`say` (built-in macOS)** — zero setup, 184 voices installed by default, AVFoundation-backed. Default voice = Samantha (decent but plain). 6/10 quality — proves the EXPERIENCE.
2. **Apple Premium / Enhanced voices** (Ava, Allison, Tom, Nicky, Zoe) — 5 min install via System Settings → Accessibility → Spoken Content → System Voice → Customize → download. Neural quality, 8/10. **Leo does NOT have these installed yet** (`defaults read com.apple.speech.voice.prefs` returns "domain does not exist").
3. **AVSpeechSynthesizer (Swift API)** — native iOS/macOS framework. Same voice pool as `say`. Built-in delegate methods `speechSynthesizer(_:willSpeakRangeOfSpeechString:utterance:)` give per-word range events for free — no whisperx forced alignment needed.
4. **Chatterbox MLX** — 30 min setup, 8.5/10, voice cloning. Apache 2.0.
5. **NeuTTS Air** — 0.5B params, designed on-device-first. Newer; less docs. Apache 2.0.
6. **XTTS-v2 (Coqui)** — 1 hr setup, mature, voice cloning works on M-series via PyTorch MPS.

Higgs Audio V2 (cloud-only, 9/10) re-enters the conversation only if all six above fail Leo's quality bar. They probably won't.

## What we're keeping vs deferring

**Keeping** (work product survives the pivot):
- `modal_app/higgs.py` — full Modal app with whisperx integration (202 lines, py_compile OK). Sits in repo as future reference if Phase 4 (full-duplex voice chat) ever needs server-side TTS.
- Modal account at `firstbitelabs` workspace — still useful for Phase 4 STT (Whisper / Parakeet).
- HF Space API surface (8 voice presets, 4 endpoints) documented in `evidence/2026-05-01-hf-space-attempt.md` — same future-Phase-4 reference value.
- Modal CLI installed at `/Users/leokwan/.local/bin/modal` — costs nothing to leave.

**Deferring** (was [pending] / [in_progress], now [blocked: deferred per pivot]):
- T3 deploy — won't run unless Phase 0 returns "Higgs needed."
- T4 whisperx verification — not needed; AVSpeechSynthesizer's word-range delegate replaces whisperx for the Mac-native path.
- T5-T6 (Higgs-specific quality samples + verdict).

## New Phase 0 (Mac-native PoC)

- **M1**: Generate `say` Samantha sample — DONE this cycle. `evidence/2026-05-01-mac-say-samantha.{aiff,m4a}`. ~12 sec, 57KB m4a.
- **M2**: Leo listens, gives experience verdict. EITHER **GO-with-Samantha** (default voice clears the bar — ship Phase 1 with no further setup) OR **NEED-PREMIUM** (Samantha works conceptually but voice quality is too plain) OR **NO-GO** (eyes-free reading isn't the use case it sounded like).
- **M3** [conditional on M2 = NEED-PREMIUM]: Install Apple Premium voices via System Settings. Generate Ava + Allison + Tom samples. Leo picks his preferred voice.
- **M4** [conditional on M2 or M3 = GO]: Decision Log entry + verdict. Phase 1 unblocked.

## Phase 1 (rewritten)

`leojkwan.com /lab/reader` — Next.js page. Two implementation options, depending on where Leo wants the audio to play:

- **Browser-only** (works on any device): Web Speech API (`SpeechSynthesisUtterance`). Same Apple voices on Safari iOS/macOS, same browser-native voices elsewhere. Word events via `boundary` event on the utterance. Zero backend.
- **Server-rendered audio** (works in any audio player): Vercel function shells out to `say -o /tmp/foo.aiff "text"`, ffmpeg converts to m4a, returns the URL. Tap-to-continue tracks word ranges from the original SSML or computed at boundaries.

Both ship with no GPU, no Modal, no cloud TTS. AVSpeechSynthesizer's word-range delegate makes whisperx forced alignment unnecessary for the local path.

## Phase 4 reconsidered

Full-duplex voice chat with vidux while walking. Still requires:
- STT: Whisper / Parakeet (Apple's SpeechAnalyzer in iOS 26+ may suffice — investigate)
- VAD: turn detection (silero-vad, ~5MB, MPS-friendly)
- LLM brain: Claude API (already have)
- TTS: AVSpeechSynthesizer is sufficient for v1; Higgs/Modal upgrade only if voice expressiveness becomes the bottleneck

So Modal is still load-bearing for STT in Phase 4 — but we don't need to deploy it now. The account is set up; we use it when Phase 4 starts.

## Cron deletion

Cron `477bdef0` was calibrated to advance the Modal path (T1-T6 task names). Post-pivot the cycle prompt is misshapen — every fire prompts "for T1 install Modal CLI, for T2 write Modal app file..." which no longer matches the M-prefix tasks. Leo should `CronDelete 477bdef0` and re-fire `/loop 30m <new prompt>` if he wants automated cycles on the Mac-native PoC.

## Sunk cost summary

- ~9 cycles of cron fires (~$0.50-1.00 of Claude API)
- 0 GPU-seconds on Modal (deploy was killed before image build completed)
- $0 Modal billing
- ~30 min of plan / file authoring (work product partially reusable)

Acceptable. The accidental Modal infrastructure becomes a Phase 4 prepayment.
