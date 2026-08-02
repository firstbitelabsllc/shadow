# Outcome-card comprehension dogfood

Date: 2026-08-02
Surface: local Vidux Outcome card at the loopback browser view
Scope: one ordinary operator read the card without opening code or agent machinery

## Observation

The operator could see that the card needed attention and could read the
declared Outcome and current move. They then asked what they were supposed to
tell the driver to unblock the work. The card showed `Steering unavailable
(409)` but did not explain the non-executing response path or name the four
answers needed for this comprehension check.

## Result

**Comprehension did not pass.** No four-answer receipt was produced. This is a
copy and guidance failure, not evidence that a live Steer, Ask, queue, or
provider runtime is needed.

## Bounded follow-up

The one-sentence host-chat instruction shipped in PR #68 and is covered by the
steering unit regression and the focused desktop/iPad/iPhone browser checks.
The correction remains non-executing: it does not add an Ask, Steer runtime,
queue, transport, or transcript store. A corrected-card human rerun is still
required; until one ordinary person supplies the four answers, comprehension
remains unproven.
