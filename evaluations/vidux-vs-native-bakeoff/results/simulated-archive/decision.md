# Bake-Off Decision

Best native arm overall: **cursor_native** (54.17% proven_resolved_rate)

## Threshold outcomes
- Keep current Vidux for mammoth/multi-session: **YES**
- Kernelize Vidux: **YES**

## Task-class routing
```text
atomic           → cursor_native
cold_resume      → current_vidux
compound         → thin_vidux_kernel
convergence      → current_vidux
plan_noise       → thin_vidux_kernel
plan_noise_stress → thin_vidux_kernel
safety           → current_vidux
safety_proof_honesty → thin_vidux_kernel
ui_runtime       → claude_native
user_visible_runtime → claude_native
```

