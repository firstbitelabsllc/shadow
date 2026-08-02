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

Add one sentence to the unavailable-Steering state telling the operator to
reply in the host chat with the Outcome, what is happening now, the next move,
and proof status. Re-run this same card check after the copy change. Do not
store a transcript or add another interaction surface.
