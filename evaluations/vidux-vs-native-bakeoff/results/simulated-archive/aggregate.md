# Bake-Off Aggregate (full)

| arm | proven_resolved_rate | p50 plan_tokens | p50 time_to_first_diff | cold_resume_min | safety_escapes |
|---|---:|---:|---:|---:|---:|
| claude_native | 54.17% | 750 | 5.0 | 20.0 | 0 |
| codex_native | 37.50% | 720 | 4.8 | 19.0 | 8 |
| current_vidux | 87.50% | 3900 | 11.0 | 6.5 | 0 |
| cursor_native | 54.17% | 700 | 4.5 | 18.0 | 4 |
| thin_vidux_kernel | 87.50% | 1050 | 7.5 | 8.0 | 0 |

## By task class
### atomic
| arm | proven_resolved_rate | runs |
|---|---:|---:|
| claude_native | 100.00% | 8 |
| codex_native | 100.00% | 8 |
| current_vidux | 100.00% | 8 |
| cursor_native | 100.00% | 8 |
| thin_vidux_kernel | 100.00% | 8 |

### cold_resume
| arm | proven_resolved_rate | runs |
|---|---:|---:|
| claude_native | 0.00% | 8 |
| codex_native | 0.00% | 8 |
| current_vidux | 100.00% | 8 |
| cursor_native | 0.00% | 8 |
| thin_vidux_kernel | 100.00% | 8 |

### compound
| arm | proven_resolved_rate | runs |
|---|---:|---:|
| claude_native | 100.00% | 10 |
| codex_native | 100.00% | 10 |
| current_vidux | 100.00% | 10 |
| cursor_native | 100.00% | 10 |
| thin_vidux_kernel | 100.00% | 10 |

### convergence
| arm | proven_resolved_rate | runs |
|---|---:|---:|
| claude_native | 0.00% | 6 |
| codex_native | 0.00% | 6 |
| current_vidux | 0.00% | 6 |
| cursor_native | 0.00% | 6 |
| thin_vidux_kernel | 0.00% | 6 |

### plan_noise
| arm | proven_resolved_rate | runs |
|---|---:|---:|
| claude_native | 0.00% | 3 |
| codex_native | 0.00% | 3 |
| current_vidux | 100.00% | 3 |
| cursor_native | 0.00% | 3 |
| thin_vidux_kernel | 100.00% | 3 |

### plan_noise_stress
| arm | proven_resolved_rate | runs |
|---|---:|---:|
| claude_native | 0.00% | 1 |
| codex_native | 0.00% | 1 |
| current_vidux | 100.00% | 1 |
| cursor_native | 0.00% | 1 |
| thin_vidux_kernel | 100.00% | 1 |

### safety
| arm | proven_resolved_rate | runs |
|---|---:|---:|
| claude_native | 0.00% | 3 |
| codex_native | 0.00% | 3 |
| current_vidux | 100.00% | 3 |
| cursor_native | 0.00% | 3 |
| thin_vidux_kernel | 100.00% | 3 |

### safety_proof_honesty
| arm | proven_resolved_rate | runs |
|---|---:|---:|
| claude_native | 0.00% | 1 |
| codex_native | 0.00% | 1 |
| current_vidux | 100.00% | 1 |
| cursor_native | 0.00% | 1 |
| thin_vidux_kernel | 100.00% | 1 |

### ui_runtime
| arm | proven_resolved_rate | runs |
|---|---:|---:|
| claude_native | 100.00% | 7 |
| codex_native | 0.00% | 7 |
| current_vidux | 100.00% | 7 |
| cursor_native | 100.00% | 7 |
| thin_vidux_kernel | 100.00% | 7 |

### user_visible_runtime
| arm | proven_resolved_rate | runs |
|---|---:|---:|
| claude_native | 100.00% | 1 |
| codex_native | 0.00% | 1 |
| current_vidux | 100.00% | 1 |
| cursor_native | 100.00% | 1 |
| thin_vidux_kernel | 100.00% | 1 |

