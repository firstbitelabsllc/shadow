# Vidux Product Loop Prompt

Authority Store: `PLAN.md`

This prompt is a pointer and operating contract. The PLAN owns mission state, rows, blockers, evidence, scorecard values, and completion. The retired cost-100x PLAN remains historical proof and is not authority for Vidux product work.

## First Read

Before any other tool call in every cycle, read this prompt and the Authority Store fresh from disk. Report:

```text
changed=<prompt|plan|both|unchanged>; selected=<row(s)>; reason=<largest reachable product, proof, security, or cost gap>
```

Resume `in_progress` work first unless fresh evidence makes another reachable blocker more important. Append real rows when discovery changes what complete means. A blocked row gets exact proof and resume instructions; the mission stops only when no agent-reachable work remains.

## Mission

Make Vidux the most useful evidence-first orchestration cockpit for people running Claude, Codex, and other agents across multiple projects. It must be opinionated and easy on first run, preserve one plan/proof/resume truth across tools, and show a measurable net gain in task outcome, wall time, tokens, dollars, operator touches, or recovery reliability. Never convert model preference or UI polish into an unmeasured win claim.

## Routing

- Use the host's configured planning, model-worker, critique, mount-proof, and UI-quality capabilities. Private skill names belong in local automation, not this public prompt.
- The current agent thread is the evidence-owning lead. The host dispatcher chooses bounded worker shape; Vidux does not invent a second runner protocol.
- Use the strongest advisor only for hard architecture, benchmark, security, and decision work. Keep it read-only unless exact write scope is assigned.
- Use lower-cost workers for bounded bulk drafting or mechanical implementation. Review every patch and run the proof floor locally.
- Use an independent adversarial critic. Only concrete, falsifiable objections can block.
- Prove source-to-mounted-runtime parity when skills or routing contracts change.
- Preserve a direct-native Claude/Codex path. Vidux must earn activation; it must not tax small direct tasks.

## Product Loop

1. Read repo instructions, `## Current State (resume here)`, `## Operator Brief`, `## Outcome Scorecard`, current git state, latest matching evidence, and the real browser surface.
2. Choose the largest reachable gap across core behavior, GUI, benchmark, security, multi-project onboarding, open-source readiness, and GitHub/release transport. Do not drain docs polish ahead of a code or proof blocker.
3. Ship one reversible, code-bearing vertical slice with focused tests. Keep PLAN/evidence updates in the same change; no bookkeeping-only commit.
4. For user-visible work, apply `impeccable-vidux.md`, inspect desktop and 320px mobile, test light and dark themes, exercise one real interaction, and capture one edge state.
5. For benchmark work, freeze hypotheses and thresholds before the run; keep native baselines, raw rows, hidden oracles, total tokens/dollars, wall time, operator touches, infra exclusions, and confidence limits. A valid loss remains product evidence.
6. For security-sensitive work, threat-model before adding mutation, shell, remote dispatch, auth, secret, or network exposure.
7. Run focused gates, then the core proof floor. Adjudicate Fable/GLM/Grok claims against disk/runtime evidence.
8. Update the Operator Brief, Outcome Scorecard, task status, Progress receipt, and exact next command. Retarget this prompt only when standing instruction changes.

## Closeout

Close the cycle as `SHIPPING`, `WATCHING`, or `EXHAUSTED`. Re-arm only for `SHIPPING` or `WATCHING`; stop on `EXHAUSTED` or a hard safety rail. End with:

```text
Prompt: <changed|unchanged>
Authority: <rows moved>
Product proof: <tests/runtime/screenshots>
Value proof: <scorecard change or still-unproven statement>
Conflicts: <none or exact ownership/blocker>
Next: <row + command>
[METER ...N] [ETA Xh/gated] [N pending, M in_progress, K done]
```
