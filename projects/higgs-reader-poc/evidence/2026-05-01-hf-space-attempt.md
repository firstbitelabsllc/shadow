# HF Space dogfood attempt — 2026-05-01

## Goal

Verify Higgs Audio V2 quality through `huggingface.co/spaces/smola/higgs_audio_v2` (free ZeroGPU tier) as a parallel-track PoC while T1's Modal OAuth is still pending. Idea: HF Space requires no auth and could deliver the verdict-eligible audio sample without Modal.

## What worked

- `gradio_client` (Python lib) installed via `uv run --with gradio_client`. Loaded the Space API, enumerated 4 endpoints.
- Full API surface captured:
  - `/generate_speech` — main endpoint. Params: `text`, `voice_preset` (literal of: belinda, broom_salesman, chadwick, en_man, en_woman, mabel, vex, zh_man_sichuan, EMPTY), `reference_audio` (filepath for voice cloning), `reference_text`, `max_completion_tokens`, `temperature`, `top_p`, `top_k`, `system_prompt`, `stop_strings`, `ras_win_len`, `ras_win_max_num_repeat`. Returns `(model_response: str, generated_audio: filepath)`.
  - `/apply_template` — load preset templates (voice-clone, smart-voice, multispeaker-voice-description, single-speaker-voice-description, single-speaker-zh, single-speaker-bgm).
  - `/play_voice_sample` — preview voice presets.
  - `/lambda` — alias entrypoint.

## What failed

Three predict() attempts to `/generate_speech` with text "Hello from Leo's Higgs proof of concept. This is a quality test." (64 chars, voice_preset=en_man), 15s sleep between attempts. All 3 returned identical error:

```
gradio_client.exceptions.AppError: No GPU was available after 60s.
Create a free account to get a higher priority in ZeroGPU queues.
```

ZeroGPU is shared across all anonymous HF users. Anonymous slots are deprioritized and the per-call queue timeout is 60s (server-side, not configurable client-side).

## Workaround paths

1. **HF account + token** — `huggingface-cli login` writes `~/.cache/huggingface/token`. Pass it to `Client(..., hf_token=...)`. Queue priority increases. Browser OAuth required (Leo's hands).
2. **HF PRO** — paid tier, dedicated GPU. Probably overkill for one-shot PoC.
3. **Skip HF Space, use Modal** — original T3 plan. Same Leo-OAuth blocker but full control, no queue, no shared infra.

## Verdict

Both PoC quality-verification paths (HF Space, Modal) require Leo's browser auth. There is no fully autonomous path for this cycle. Recommend Leo proceed with Modal (`! modal token new`) since that's the path Phase 1 needs anyway — HF Space would be throwaway infra for one verdict.

## Cron-loop policy

Future cycles should NOT re-attempt HF Space until either:
- An HF token lands at `~/.cache/huggingface/token` or `$HF_TOKEN`
- Or it's been ≥6h since this attempt (queue conditions may improve)

If neither: skip the path entirely, focus on Modal.
