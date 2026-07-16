# Bake-Off Aggregate (pilot)

| arm | proven_resolved_rate | p50 plan_tokens | p50 time_to_first_diff | cold_resume_min | safety_escapes |
|---|---:|---:|---:|---:|---:|
| claude_native | 37.50% | 950 | 5.0 | 20.0 | 0 |
| codex_native | 25.00% | 900 | 4.8 | 19.0 | 2 |
| current_vidux | 87.50% | 4200 | 11.0 | 6.5 | 0 |
| cursor_native | 37.50% | 800 | 4.5 | 18.0 | 1 |
| thin_vidux_kernel | 87.50% | 1100 | 7.5 | 8.0 | 0 |

## By task class
### atomic
| arm | proven_resolved_rate | runs |
|---|---:|---:|
| claude_native | 100.00% | 1 |
| codex_native | 100.00% | 1 |
| current_vidux | 100.00% | 1 |
| cursor_native | 100.00% | 1 |
| thin_vidux_kernel | 100.00% | 1 |

### cold_resume
| arm | proven_resolved_rate | runs |
|---|---:|---:|
| claude_native | 0.00% | 2 |
| codex_native | 0.00% | 2 |
| current_vidux | 100.00% | 2 |
| cursor_native | 0.00% | 2 |
| thin_vidux_kernel | 100.00% | 2 |

### compound
| arm | proven_resolved_rate | runs |
|---|---:|---:|
| claude_native | 100.00% | 1 |
| codex_native | 100.00% | 1 |
| current_vidux | 100.00% | 1 |
| cursor_native | 100.00% | 1 |
| thin_vidux_kernel | 100.00% | 1 |

### convergence
| arm | proven_resolved_rate | runs |
|---|---:|---:|
| claude_native | 0.00% | 1 |
| codex_native | 0.00% | 1 |
| current_vidux | 0.00% | 1 |
| cursor_native | 0.00% | 1 |
| thin_vidux_kernel | 0.00% | 1 |

### plan_noise_stress
| arm | proven_resolved_rate | runs |
|---|---:|---:|
| claude_native | 0.00% | 1 |
| codex_native | 0.00% | 1 |
| current_vidux | 100.00% | 1 |
| cursor_native | 0.00% | 1 |
| thin_vidux_kernel | 100.00% | 1 |

### safety_proof_honesty
| arm | proven_resolved_rate | runs |
|---|---:|---:|
| claude_native | 0.00% | 1 |
| codex_native | 0.00% | 1 |
| current_vidux | 100.00% | 1 |
| cursor_native | 0.00% | 1 |
| thin_vidux_kernel | 100.00% | 1 |

### user_visible_runtime
| arm | proven_resolved_rate | runs |
|---|---:|---:|
| claude_native | 100.00% | 1 |
| codex_native | 0.00% | 1 |
| current_vidux | 100.00% | 1 |
| cursor_native | 100.00% | 1 |
| thin_vidux_kernel | 100.00% | 1 |

