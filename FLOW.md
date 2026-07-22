# Leo Flow

Local runtime projection for the active Leo Flow run. PLAN.md, FLOW.md, and the ledger own state; this file records Flow routing, receipts, open gates, and the next safe action.

- Run: `flow-20260721T222003Z-11498b9b`
- Status: `active`
- Request: Design ABC to FIRE Vidux control plane with Claude Fable; read-only planning; fold draft into plans/abc-fire-control-plane

```json
{
  "authority_fingerprint": {
    "bytes": 3442,
    "exists": true,
    "kind": "plan",
    "mtime_ns": 1784672403362146844,
    "path": "/Users/leokwan/Development/vidux-main-active/plans/abc-fire-control-plane/PLAN.md",
    "read_at": "2026-07-21T22:20:03Z",
    "read_status": "ok",
    "sha256": "572f0a40eda13fbe76e67fa1e9e83c0659d5de8d335b4cf5d843945e49b4538a"
  },
  "code_intent_explicit": false,
  "context": {
    "authority_fingerprint": {
      "bytes": 3442,
      "exists": true,
      "kind": "plan",
      "mtime_ns": 1784672403362146844,
      "path": "/Users/leokwan/Development/vidux-main-active/plans/abc-fire-control-plane/PLAN.md",
      "read_at": "2026-07-21T22:20:03Z",
      "read_status": "ok",
      "sha256": "572f0a40eda13fbe76e67fa1e9e83c0659d5de8d335b4cf5d843945e49b4538a"
    },
    "code_intent_explicit": false,
    "hard_wall_hits": [],
    "hard_walls": [
      "destructive_git",
      "human_directed_message",
      "teammate_mention",
      "merge_without_live_policy",
      "money_or_security_change",
      "direct_prod_mutation_without_policy",
      "snap_data_outside_internal_surfaces",
      "browser_signin_required",
      "conflicting_unowned_worktree_state"
    ],
    "lane_ids": [
      "voice"
    ],
    "proof_floors": {
      "voice": "current_artifact_or_diff_context"
    },
    "repo": "/Users/leokwan/Development/vidux-main-active",
    "request": "Design ABC to FIRE Vidux control plane with Claude Fable; read-only planning; fold draft into plans/abc-fire-control-plane",
    "state_source": "/Users/leokwan/Development/vidux-main-active/plans/abc-fire-control-plane/PLAN.md",
    "steering_contract": {
      "ack_requires": [
        "plan_receipt",
        "response_receipt"
      ],
      "authority_sha256": "572f0a40eda13fbe76e67fa1e9e83c0659d5de8d335b4cf5d843945e49b4538a",
      "boundary_order": [
        "fresh_authority_read",
        "lease_one",
        "apply_plan_consequence",
        "rank_work",
        "execute",
        "user_facing_response",
        "acknowledge"
      ],
      "delivery_failure": "visible_retryable_no_ack",
      "disabled_reason": null,
      "enabled": true,
      "idempotency_key": "envelope_id",
      "max_items_per_boundary": 1,
      "mutation_surface": "none",
      "plan_consequence": "required_before_rank",
      "projection_only": true,
      "provider_neutral": true,
      "requires_plan": true,
      "schema": "leo-flow.steering-boundary.v1",
      "transport": "adapter_owned"
    },
    "subagent_plan": {
      "cost_policy": {
        "default_worker": "glm_max_worker",
        "direct_local_rule": "Do tiny tightly coupled edits directly when delegation setup and review would cost more than the edit.",
        "escalation": {
          "enter_planner_when": "hard_risk_or_receipt_backed_miss",
          "next_tier_requires": [
            "failure_class",
            "receipt_locator",
            "bounded_next_attempt"
          ],
          "order": [
            "glm_max_worker",
            "codex_luna_worker",
            "grok_max_worker",
            "cursor_worker",
            "codex_sol_worker",
            "planner_tier"
          ],
          "quota_fallback": "codex_terra_worker is selected only on a codex_sol_worker weekly-quota-limit receipt; otherwise Terra is off the ladder (Leo 2026-07-18: point Codex delegation at Sol instead of Terra).",
          "receipt_backed_miss_results": [
            "fail",
            "blocked",
            "auth_gap",
            "source_gap"
          ],
          "required_receipt_fields": [
            "source",
            "result",
            "claim",
            "ts"
          ],
          "retry_budget_per_tier": 1
        },
        "independent_review_worker": "grok_max_worker",
        "objective": "cost_per_completed_task",
        "owner": "leo-flow_compatibility",
        "policy": "Use the cheapest capable path, count retries and lead-review cost, and escalate only for a named hard boundary or a receipt-backed miss. Pilot owns the routing decision; Flow projects the compatibility schema; /delegate owns provider transport and private account selection.",
        "provider_quota": {
          "adapter": "/Users/leokwan/.ai/skills-active/delegate/scripts/provider-quota",
          "adapter_exit": 0,
          "cache": {
            "age_seconds": 0,
            "status": "hit",
            "ttl_seconds": 900
          },
          "measured_at": "2026-07-21T22:20:05Z",
          "providers": {
            "grok": {
              "contract": "installed_cli_internal",
              "period_start": "2026-07-18T11:22:08.274381Z",
              "remaining_percent": 90.0,
              "reset_at": "2026-07-25T11:22:08.274381Z",
              "source": "grok_build_billing_api",
              "status": "ok",
              "usage_percent": 10.0
            },
            "zai": {
              "accounts": [
                {
                  "account": "account_1",
                  "limits": {
                    "five_hour": {
                      "current_value": null,
                      "limit_value": null,
                      "remaining_percent": 65.0,
                      "reset_at": "2026-07-22T02:22:27.984000Z",
                      "usage_percent": 35.0
                    },
                    "monthly_tools": {
                      "current_value": 341,
                      "limit_value": 4000,
                      "remaining_percent": 92.0,
                      "reset_at": "2026-07-24T02:22:27.997000Z",
                      "usage_percent": 8.0
                    },
                    "weekly": {
                      "current_value": null,
                      "limit_value": null,
                      "remaining_percent": 99.0,
                      "reset_at": "2026-07-22T03:17:18.337000Z",
                      "usage_percent": 1.0
                    }
                  },
                  "status": "ok"
                },
                {
                  "account": "account_2",
                  "limits": {
                    "five_hour": {
                      "current_value": null,
                      "limit_value": null,
                      "remaining_percent": 100.0,
                      "reset_at": null,
                      "usage_percent": 0.0
                    },
                    "monthly_tools": {
                      "current_value": 0,
                      "limit_value": 4000,
                      "remaining_percent": 100.0,
                      "reset_at": "2026-07-25T07:23:38.979000Z",
                      "usage_percent": 0.0
                    },
                    "weekly": {
                      "current_value": null,
                      "limit_value": null,
                      "remaining_percent": 91.0,
                      "reset_at": "2026-07-23T07:23:38.997000Z",
                      "usage_percent": 9.0
                    }
                  },
                  "status": "ok"
                }
              ],
              "source": "zai_quota_api",
              "status": "ok"
            }
          },
          "routing": {
            "recommended_workers": [
              "glm_max_worker",
              "grok_max_worker"
            ],
            "rule": "prefer paid code workers with healthy coding quota; Z.ai monthly tools are excluded; capability and proof policy still apply",
            "worker_state": {
              "glm_max_worker": {
                "account_count": 2,
                "effective_remaining_percent": 91.0,
                "healthy_account_count": 2,
                "known_account_count": 2,
                "lowest_remaining_percent": 65.0,
                "quota_basis": "five_hour+weekly",
                "state": "prefer"
              },
              "grok_max_worker": {
                "effective_remaining_percent": 90.0,
                "lowest_remaining_percent": 90.0,
                "quota_basis": "billing_period",
                "state": "prefer"
              }
            }
          },
          "schema": "provider-quota.v1"
        },
        "provider_transport": "delegate/cost-route",
        "routing_owner": "pilot",
        "schema": "leo-flow.cost-policy.v1",
        "sol_ultra": {
          "auto_select": "never",
          "default": "disabled",
          "definition": "GPT-5.6 Sol with xhigh/ultra reasoning or an equivalent highest-cost Sol route.",
          "reason": "High cost and overthinking risk; no measured cost-per-completed-task advantage.",
          "reconsider_only_when": "The current user explicitly requests it, cheaper tiers have receipt-backed misses, and a verified adapter plus bounded budget exists."
        },
        "stop_reasoning": {
          "max_unproven_replans": 1,
          "next_step": "execute_or_collect_missing_receipt",
          "rule": "Stop planning when a deterministic gate settles the question or the first safe proofable move is named."
        },
        "usage_visibility": {
          "never_infer_quota_remaining": true,
          "portable_fields": [
            "input_tokens",
            "output_tokens",
            "cache_read_tokens",
            "cache_write_tokens",
            "context_tokens",
            "turns",
            "cost_usd",
            "quota_remaining",
            "quota_unit",
            "source",
            "measured_at"
          ],
          "unknown_value": null
        }
      },
      "delegation_policy": {
        "assignment_sink": "Write leader/follower assignment into FLOW.md, the owning PLAN.md claim/progress line, or the ledger; do not encode model routing in a second queue.",
        "mail_policy": "Mail: Superhuman Mail MCP only \u2014 never Gmail MCP (gmail__*, gmail-personal, gmail-fbl, raw ~/.gmail-mcp). Subagents included. If Superhuman is not set up, blocked_with_resume and set up Superhuman; do not fall back to Gmail.",
        "max_sidecars": 3,
        "no_overlap_rule": "Workers must own disjoint file sets; read-only scouts must not edit; writable workers edit only allowed_paths.",
        "single_plan_rule": "Every runner reads the same Authority Store, claims disjoint allowed_paths or read-only scope, writes receipts/foldback, and never creates a shadow queue.",
        "wait_rule": "Do not wait unless the next local action or merge/proof boundary is blocked on that answer."
      },
      "generated_at": "2026-07-21T22:20:05Z",
      "hours": 4.0,
      "lead": {
        "eligible_runners": [
          "codex_headless",
          "claude_code",
          "cursor_agent",
          "grok_build",
          "fable_planner"
        ],
        "id": "lead",
        "owner": "current agent",
        "rule": "The lead keeps coordination, safety, and acceptance local; Fable owns planner-tier work only when selected by a hard-boundary or receipt-backed escalation; Z.ai/GLM, Codex Luna, Grok, and Codex Sol writable followers may drive assigned disjoint implementation slices and fold back receipts before any merge/claim.",
        "selection": "Pick the runner with the best current tools, context, cost, and proof path for the mission; lead is a role, not a fixed hierarchy.",
        "task": "Run boot_safety locally, keep hard planning and acceptance on the planner/lead tier, and assign disjoint write-scoped slices to Z.ai/GLM or Codex Luna first; add bounded Grok critique or Cursor only when the task or a receipt-backed miss justifies it."
      },
      "leader_follower": {
        "assignment_sink": "Write leader/follower assignment into FLOW.md, the owning PLAN.md claim/progress line, or the ledger; do not encode model routing in a second queue.",
        "authority_boundary": "Vidux PLAN.md owns durable project state and Ledger owns append-only evidence; Pilot owns leader/follower orchestration, runner selection, scope assignment, foldback validation, and lead acceptance. Leo Flow preserves the compatibility schema.",
        "claude_lead": "Claude Code can drive when it owns the strongest live context or tool surface; Pilot still records assignment, claims, and proof foldback.",
        "codex_headless": "Codex can run headless as lead or sidecar; it must still read the Authority Store first and fold receipts back through Pilot.",
        "codex_native_rule": "Codex is a first-class lead: prefer its native worker/explorer collaboration lifecycle for eligible local work, not a shell-spawned Codex imitation. gpt-5.3-codex-spark never selects by default because it uses a separate usage class; only an explicit user request opens it.",
        "compatibility_implementation": "leo-flow",
        "driver_agnostic": "The driver seat is role-based, never brand-based (Leo 2026-07-18): Claude Code, Cursor, Grok Build, or headless Codex may lead per lead_selection. One harness, many models - model backends swap per task while the Authority Store, claims, and receipt foldback stay identical for every driver.",
        "escalation_rule": "Escalate only for a named hard boundary or a receipt-backed miss; one unproven re-plan is the limit before executing the first safe proofable move.",
        "follower_runners": [
          "codex_headless",
          "claude_code",
          "glm_max_worker",
          "codex_luna_worker",
          "grok_max_worker",
          "cursor_worker",
          "codex_sol_worker",
          "source_scout",
          "counter_review",
          "proof_audit"
        ],
        "host_native_rule": "When /pilot is loaded and eligible work has a useful disjoint, context-isolating, or independent-proof slice, the current host uses native subagents without waiting for a second delegation prompt. Maximum three followers, depth one; the lead inspects diffs, runs proof, folds receipts, and closes idle workers.",
        "lead_runners": [
          "codex_headless",
          "claude_code",
          "cursor_agent",
          "grok_build",
          "fable_planner"
        ],
        "lead_selection": "Pick the runner with the best current tools, context, cost, and proof path for the mission; lead is a role, not a fixed hierarchy.",
        "model_worker_default": "Safe non-trivial code defaults to bounded Z.ai/GLM implementation; use Codex Luna for a small first-party slice, Grok for bounded independent critique or an alternate, and Codex Sol for one hard well-bounded implementation slice after a receipt-backed miss (sole task doer - never orchestration); Codex Terra only on a Sol weekly-quota-limit receipt. Workers do not own planning or acceptance.",
        "owner": "pilot",
        "pilot_driver_contract": "skills/pilot/driver.json owns the portable host-native supervisory loop; this Flow contract remains the compatibility routing, scope, and receipt kernel.",
        "single_plan_rule": "Every runner reads the same Authority Store, claims disjoint allowed_paths or read-only scope, writes receipts/foldback, and never creates a shadow queue."
      },
      "mail_policy": "Mail: Superhuman Mail MCP only \u2014 never Gmail MCP (gmail__*, gmail-personal, gmail-fbl, raw ~/.gmail-mcp). Subagents included. If Superhuman is not set up, blocked_with_resume and set up Superhuman; do not fall back to Gmail.",
      "mutation_surface": "none",
      "next_action": "Start sidecars only after the lead has a non-overlapping local task.",
      "planning_tier": {
        "acceptance_owner": "current lead",
        "activation_gate": "explicit_request_or_receipt_backed_cheaper_tier_miss",
        "owner": "pilot",
        "planners": [
          {
            "activation": "explicit_request_or_receipt_backed_cheaper_tier_miss",
            "auto_select": false,
            "availability": "host_resolved",
            "binding": "host skill /fable (Claude/Fable planner tier)",
            "id": "fable",
            "role": "architecture_test_strategy_and_independent_review",
            "skill": "fable",
            "source_gap": null
          },
          {
            "activation": "redirect_to_codex_sol_worker",
            "auto_select": false,
            "availability": false,
            "binding": "workers: codex_sol_worker (first-party codex exec adapter, verified 2026-07-18)",
            "id": "sol",
            "role": "worker_only_never_orchestrator",
            "skill": "pilot",
            "source_gap": "sol_is_worker_tier_by_user_verdict"
          },
          {
            "activation": "disabled_by_cost_policy",
            "auto_select": false,
            "availability": false,
            "binding": null,
            "id": "sol_ultra",
            "role": "exceptional_last_resort_review_only",
            "skill": null,
            "source_gap": "sol_ultra_disabled_by_cost_policy"
          }
        ],
        "policy": "The current lead owns ordinary planning and final acceptance. Fable is an explicit or receipt-backed escalation for genuinely hard work; Z.ai/GLM and Grok are bounded implementation workers. Generic plan/planning or broad wording may recommend planning but never auto-spends a premium planner call.",
        "recommended": false,
        "requested": [
          "fable"
        ],
        "required": true,
        "selected": [
          "fable"
        ],
        "source_gaps": []
      },
      "projection_only": true,
      "quota_routing": {
        "alignment": "not_applicable",
        "applicable": false,
        "missing_recommended_workers": [],
        "projected_workers": [],
        "recommended_workers": [
          "glm_max_worker",
          "grok_max_worker"
        ]
      },
      "repo": "/Users/leokwan/Development/vidux-main-active",
      "request": "Design ABC to FIRE Vidux control plane with Claude Fable; read-only planning; fold draft into plans/abc-fire-control-plane",
      "roster": {
        "path": "/Users/leokwan/.ai/skills-active/pilot-leo/roster.yaml",
        "persona": "personal",
        "sha256": "a0e69d9b50cdb5b9197ae8544fffc2b94b50e5051f250321e097b2a35c7bd6c8"
      },
      "route": {
        "blocked_by_hard_walls": false,
        "code_intent_explicit": false,
        "hard_wall_hits": [],
        "lane_ids": [
          "voice"
        ],
        "proof_floors": {
          "voice": "current_artifact_or_diff_context"
        },
        "skills": [
          "crashcourse",
          "slop"
        ]
      },
      "schema": "leo-flow.subagents.v1",
      "sidecars": [
        {
          "agent_type": "evidence_gatherer",
          "allowed_paths": [],
          "branch": null,
          "command_hint": null,
          "context_paths": [],
          "context_sha256": {},
          "foldback_target": "FLOW.md",
          "follower_default": null,
          "id": "source_scout",
          "invocation_blocker": null,
          "invocation_branch": null,
          "invocation_git_common_dir": null,
          "invocation_head": null,
          "invocation_ready": false,
          "invocation_worktree": null,
          "lanes": [
            "snap",
            "queue",
            "review",
            "teach",
            "risk"
          ],
          "lead_eligible": null,
          "matched_hints": [],
          "matched_lanes": [],
          "mode": "research",
          "model_tier": null,
          "output": "cited_source_snapshot",
          "prompt": "Scope: source_scout for Leo Flow request 'Design ABC to FIRE Vidux control plane with Claude Fable; read-only planning; fold draft into plans/abc-fire-control-plane' in /Users/leokwan/Development/vidux-main-active. Mode: research. Lanes: snap, queue, review, teach, risk. Output: cited_source_snapshot. Skill: none. Model tier: n/a. Strength profile: n/a. Command hint: n/a. Receipt contract: sources, owners, open questions, and source_gap items only. Spawn contract: standard sidecar contract. Foldback target: FLOW.md. Write scope: none. Worktree: none. Branch: none. Allowed paths: none. Write blocker: none. Invocation ready: false. Read-only provider context: none. Mail: Superhuman Mail MCP only \u2014 never Gmail MCP (gmail__*, gmail-personal, gmail-fbl, raw ~/.gmail-mcp). Subagents included. If Superhuman is not set up, blocked_with_resume and set up Superhuman; do not fall back to Gmail. Only write inside the declared write scope; do not revert others' work; fold back to the parent/lead before any merge or claim; return concrete receipts, gaps, and next action.",
          "receipt_contract": "sources, owners, open questions, and source_gap items only.",
          "score": 4,
          "skill": null,
          "spawn_contract": null,
          "strength_profile": null,
          "wait": "Do not wait unless the next local action or merge/proof boundary is blocked on that answer.",
          "worktree": null,
          "write_blocker": null,
          "write_ready": false,
          "write_scope": "none"
        },
        {
          "agent_type": "pr_researcher",
          "allowed_paths": [],
          "branch": null,
          "command_hint": null,
          "context_paths": [],
          "context_sha256": {},
          "foldback_target": "FLOW.md",
          "follower_default": null,
          "id": "counter_review",
          "invocation_blocker": null,
          "invocation_branch": null,
          "invocation_git_common_dir": null,
          "invocation_head": null,
          "invocation_ready": false,
          "invocation_worktree": null,
          "lanes": [
            "review",
            "proof",
            "voice",
            "nurse"
          ],
          "lead_eligible": null,
          "matched_hints": [],
          "matched_lanes": [
            "voice"
          ],
          "mode": "research",
          "model_tier": null,
          "output": "stale_comment_or_major_risk_audit",
          "prompt": "Scope: counter_review for Leo Flow request 'Design ABC to FIRE Vidux control plane with Claude Fable; read-only planning; fold draft into plans/abc-fire-control-plane' in /Users/leokwan/Development/vidux-main-active. Mode: research. Lanes: voice. Output: stale_comment_or_major_risk_audit. Skill: none. Model tier: n/a. Strength profile: n/a. Command hint: n/a. Receipt contract: PR head/ref, file lines, review thread state, CI/check state, and residual risk. Spawn contract: standard sidecar contract. Foldback target: FLOW.md. Write scope: none. Worktree: none. Branch: none. Allowed paths: none. Write blocker: none. Invocation ready: false. Read-only provider context: none. Mail: Superhuman Mail MCP only \u2014 never Gmail MCP (gmail__*, gmail-personal, gmail-fbl, raw ~/.gmail-mcp). Subagents included. If Superhuman is not set up, blocked_with_resume and set up Superhuman; do not fall back to Gmail. Only write inside the declared write scope; do not revert others' work; fold back to the parent/lead before any merge or claim; return concrete receipts, gaps, and next action.",
          "receipt_contract": "PR head/ref, file lines, review thread state, CI/check state, and residual risk.",
          "score": 4,
          "skill": null,
          "spawn_contract": null,
          "strength_profile": null,
          "wait": "Do not wait unless the next local action or merge/proof boundary is blocked on that answer.",
          "worktree": null,
          "write_blocker": null,
          "write_ready": false,
          "write_scope": "none"
        },
        {
          "agent_type": "explorer",
          "allowed_paths": [],
          "branch": null,
          "command_hint": null,
          "context_paths": [],
          "context_sha256": {},
          "foldback_target": "FLOW.md",
          "follower_default": null,
          "id": "proof_audit",
          "invocation_blocker": null,
          "invocation_branch": null,
          "invocation_git_common_dir": null,
          "invocation_head": null,
          "invocation_ready": false,
          "invocation_worktree": null,
          "lanes": [
            "build",
            "proof",
            "ios",
            "music-backend"
          ],
          "lead_eligible": null,
          "matched_hints": [],
          "matched_lanes": [],
          "mode": "research",
          "model_tier": null,
          "output": "proof_gap_and_test_plan",
          "prompt": "Scope: proof_audit for Leo Flow request 'Design ABC to FIRE Vidux control plane with Claude Fable; read-only planning; fold draft into plans/abc-fire-control-plane' in /Users/leokwan/Development/vidux-main-active. Mode: research. Lanes: build, proof, ios, music-backend. Output: proof_gap_and_test_plan. Skill: none. Model tier: n/a. Strength profile: n/a. Command hint: n/a. Receipt contract: Exact commands, expected proof claim, skipped gates, and missing runtime/visual proof. Spawn contract: standard sidecar contract. Foldback target: FLOW.md. Write scope: none. Worktree: none. Branch: none. Allowed paths: none. Write blocker: none. Invocation ready: false. Read-only provider context: none. Mail: Superhuman Mail MCP only \u2014 never Gmail MCP (gmail__*, gmail-personal, gmail-fbl, raw ~/.gmail-mcp). Subagents included. If Superhuman is not set up, blocked_with_resume and set up Superhuman; do not fall back to Gmail. Only write inside the declared write scope; do not revert others' work; fold back to the parent/lead before any merge or claim; return concrete receipts, gaps, and next action.",
          "receipt_contract": "Exact commands, expected proof claim, skipped gates, and missing runtime/visual proof.",
          "score": 2,
          "skill": null,
          "spawn_contract": null,
          "strength_profile": null,
          "wait": "Do not wait unless the next local action or merge/proof boundary is blocked on that answer.",
          "worktree": null,
          "write_blocker": null,
          "write_ready": false,
          "write_scope": "none"
        }
      ],
      "stop_required": false,
      "weakest_proof_claim": "source_gap"
    }
  },
  "created_at": "2026-07-21T22:20:03Z",
  "cycle": [
    "resolve_state",
    "fresh_authority_read",
    "inspect_live_work_claims",
    "claim_one_work_surface",
    "project_steering_boundary",
    "classify",
    "dispatch",
    "collect_receipts",
    "checkpoint"
  ],
  "events": [
    {
      "next_action": null,
      "open_gates": [],
      "proof_claim": "not_proven",
      "receipts": [],
      "status": "active",
      "summary": "Started Flow run for: Design ABC to FIRE Vidux control plane with Claude Fable; read-only planning; fold draft into plans/abc-fire-control-plane",
      "ts": "2026-07-21T22:20:03Z",
      "type": "start"
    },
    {
      "cleared_open_gates": false,
      "next_action": "Leo locks or vetoes Option A",
      "open_gates": [],
      "proof_claim": "not_proven",
      "receipts": [
        {
          "artifact": "plans/abc-fire-control-plane/evidence/grok-build-high-plan-draft.md",
          "claim": "not_proven",
          "note": "planning draft only",
          "result": "pass",
          "source": "grok",
          "ts": "2026-07-21T22:26:12Z"
        }
      ],
      "status": "active",
      "summary": "Grok build/high planning draft folded; Option A recommended; awaiting Leo lock/veto",
      "ts": "2026-07-21T22:26:12Z",
      "type": "checkpoint"
    }
  ],
  "flow_path": "/Users/leokwan/Development/vidux-main-active/FLOW.md",
  "hard_wall_hits": [],
  "hard_walls": [
    "destructive_git",
    "human_directed_message",
    "teammate_mention",
    "merge_without_live_policy",
    "money_or_security_change",
    "direct_prod_mutation_without_policy",
    "snap_data_outside_internal_surfaces",
    "browser_signin_required",
    "conflicting_unowned_worktree_state"
  ],
  "lane_ids": [
    "voice"
  ],
  "lanes": [
    {
      "id": "voice",
      "output": "paste_ready_draft_or_patch",
      "proof_floor": "current_artifact_or_diff_context",
      "skills": [
        "slop",
        "crashcourse"
      ]
    }
  ],
  "proof_floors": {
    "voice": "current_artifact_or_diff_context"
  },
  "repo": "/Users/leokwan/Development/vidux-main-active",
  "request": "Design ABC to FIRE Vidux control plane with Claude Fable; read-only planning; fold draft into plans/abc-fire-control-plane",
  "result": {
    "actions": [
      {
        "summary": "Grok build/high planning draft folded; Option A recommended; awaiting Leo lock/veto",
        "ts": "2026-07-21T22:26:12Z",
        "type": "checkpoint"
      }
    ],
    "next_action": "Leo locks or vetoes Option A",
    "open_gates": [],
    "proof_claim": "not_proven",
    "receipts": [
      {
        "artifact": "plans/abc-fire-control-plane/evidence/grok-build-high-plan-draft.md",
        "claim": "not_proven",
        "note": "planning draft only",
        "result": "pass",
        "source": "grok",
        "ts": "2026-07-21T22:26:12Z"
      }
    ],
    "sidecar_receipts": [],
    "sidecar_status_events": [],
    "sidecars": [
      {
        "agent_type": "evidence_gatherer",
        "allowed_paths": [],
        "branch": null,
        "command_hint": null,
        "context_paths": [],
        "context_sha256": {},
        "foldback_target": "FLOW.md",
        "follower_default": null,
        "id": "source_scout",
        "invocation_blocker": null,
        "invocation_branch": null,
        "invocation_git_common_dir": null,
        "invocation_head": null,
        "invocation_ready": false,
        "invocation_worktree": null,
        "lanes": [
          "snap",
          "queue",
          "review",
          "teach",
          "risk"
        ],
        "lead_eligible": null,
        "matched_hints": [],
        "matched_lanes": [],
        "mode": "research",
        "model_tier": null,
        "output": "cited_source_snapshot",
        "prompt": "Scope: source_scout for Leo Flow request 'Design ABC to FIRE Vidux control plane with Claude Fable; read-only planning; fold draft into plans/abc-fire-control-plane' in /Users/leokwan/Development/vidux-main-active. Mode: research. Lanes: snap, queue, review, teach, risk. Output: cited_source_snapshot. Skill: none. Model tier: n/a. Strength profile: n/a. Command hint: n/a. Receipt contract: sources, owners, open questions, and source_gap items only. Spawn contract: standard sidecar contract. Foldback target: FLOW.md. Write scope: none. Worktree: none. Branch: none. Allowed paths: none. Write blocker: none. Invocation ready: false. Read-only provider context: none. Mail: Superhuman Mail MCP only \u2014 never Gmail MCP (gmail__*, gmail-personal, gmail-fbl, raw ~/.gmail-mcp). Subagents included. If Superhuman is not set up, blocked_with_resume and set up Superhuman; do not fall back to Gmail. Only write inside the declared write scope; do not revert others' work; fold back to the parent/lead before any merge or claim; return concrete receipts, gaps, and next action.",
        "receipt_contract": "sources, owners, open questions, and source_gap items only.",
        "score": 4,
        "skill": null,
        "spawn_contract": null,
        "strength_profile": null,
        "wait": "Do not wait unless the next local action or merge/proof boundary is blocked on that answer.",
        "worktree": null,
        "write_blocker": null,
        "write_ready": false,
        "write_scope": "none"
      },
      {
        "agent_type": "pr_researcher",
        "allowed_paths": [],
        "branch": null,
        "command_hint": null,
        "context_paths": [],
        "context_sha256": {},
        "foldback_target": "FLOW.md",
        "follower_default": null,
        "id": "counter_review",
        "invocation_blocker": null,
        "invocation_branch": null,
        "invocation_git_common_dir": null,
        "invocation_head": null,
        "invocation_ready": false,
        "invocation_worktree": null,
        "lanes": [
          "review",
          "proof",
          "voice",
          "nurse"
        ],
        "lead_eligible": null,
        "matched_hints": [],
        "matched_lanes": [
          "voice"
        ],
        "mode": "research",
        "model_tier": null,
        "output": "stale_comment_or_major_risk_audit",
        "prompt": "Scope: counter_review for Leo Flow request 'Design ABC to FIRE Vidux control plane with Claude Fable; read-only planning; fold draft into plans/abc-fire-control-plane' in /Users/leokwan/Development/vidux-main-active. Mode: research. Lanes: voice. Output: stale_comment_or_major_risk_audit. Skill: none. Model tier: n/a. Strength profile: n/a. Command hint: n/a. Receipt contract: PR head/ref, file lines, review thread state, CI/check state, and residual risk. Spawn contract: standard sidecar contract. Foldback target: FLOW.md. Write scope: none. Worktree: none. Branch: none. Allowed paths: none. Write blocker: none. Invocation ready: false. Read-only provider context: none. Mail: Superhuman Mail MCP only \u2014 never Gmail MCP (gmail__*, gmail-personal, gmail-fbl, raw ~/.gmail-mcp). Subagents included. If Superhuman is not set up, blocked_with_resume and set up Superhuman; do not fall back to Gmail. Only write inside the declared write scope; do not revert others' work; fold back to the parent/lead before any merge or claim; return concrete receipts, gaps, and next action.",
        "receipt_contract": "PR head/ref, file lines, review thread state, CI/check state, and residual risk.",
        "score": 4,
        "skill": null,
        "spawn_contract": null,
        "strength_profile": null,
        "wait": "Do not wait unless the next local action or merge/proof boundary is blocked on that answer.",
        "worktree": null,
        "write_blocker": null,
        "write_ready": false,
        "write_scope": "none"
      },
      {
        "agent_type": "explorer",
        "allowed_paths": [],
        "branch": null,
        "command_hint": null,
        "context_paths": [],
        "context_sha256": {},
        "foldback_target": "FLOW.md",
        "follower_default": null,
        "id": "proof_audit",
        "invocation_blocker": null,
        "invocation_branch": null,
        "invocation_git_common_dir": null,
        "invocation_head": null,
        "invocation_ready": false,
        "invocation_worktree": null,
        "lanes": [
          "build",
          "proof",
          "ios",
          "music-backend"
        ],
        "lead_eligible": null,
        "matched_hints": [],
        "matched_lanes": [],
        "mode": "research",
        "model_tier": null,
        "output": "proof_gap_and_test_plan",
        "prompt": "Scope: proof_audit for Leo Flow request 'Design ABC to FIRE Vidux control plane with Claude Fable; read-only planning; fold draft into plans/abc-fire-control-plane' in /Users/leokwan/Development/vidux-main-active. Mode: research. Lanes: build, proof, ios, music-backend. Output: proof_gap_and_test_plan. Skill: none. Model tier: n/a. Strength profile: n/a. Command hint: n/a. Receipt contract: Exact commands, expected proof claim, skipped gates, and missing runtime/visual proof. Spawn contract: standard sidecar contract. Foldback target: FLOW.md. Write scope: none. Worktree: none. Branch: none. Allowed paths: none. Write blocker: none. Invocation ready: false. Read-only provider context: none. Mail: Superhuman Mail MCP only \u2014 never Gmail MCP (gmail__*, gmail-personal, gmail-fbl, raw ~/.gmail-mcp). Subagents included. If Superhuman is not set up, blocked_with_resume and set up Superhuman; do not fall back to Gmail. Only write inside the declared write scope; do not revert others' work; fold back to the parent/lead before any merge or claim; return concrete receipts, gaps, and next action.",
        "receipt_contract": "Exact commands, expected proof claim, skipped gates, and missing runtime/visual proof.",
        "score": 2,
        "skill": null,
        "spawn_contract": null,
        "strength_profile": null,
        "wait": "Do not wait unless the next local action or merge/proof boundary is blocked on that answer.",
        "worktree": null,
        "write_blocker": null,
        "write_ready": false,
        "write_scope": "none"
      }
    ],
    "verdict": "active"
  },
  "run_id": "flow-20260721T222003Z-11498b9b",
  "schema": "leo-flow.run.v1",
  "skills": [
    "crashcourse",
    "slop"
  ],
  "state_source": "/Users/leokwan/Development/vidux-main-active/plans/abc-fire-control-plane/PLAN.md",
  "status": "active",
  "steering_contract": {
    "ack_requires": [
      "plan_receipt",
      "response_receipt"
    ],
    "authority_sha256": "572f0a40eda13fbe76e67fa1e9e83c0659d5de8d335b4cf5d843945e49b4538a",
    "boundary_order": [
      "fresh_authority_read",
      "lease_one",
      "apply_plan_consequence",
      "rank_work",
      "execute",
      "user_facing_response",
      "acknowledge"
    ],
    "delivery_failure": "visible_retryable_no_ack",
    "disabled_reason": null,
    "enabled": true,
    "idempotency_key": "envelope_id",
    "max_items_per_boundary": 1,
    "mutation_surface": "none",
    "plan_consequence": "required_before_rank",
    "projection_only": true,
    "provider_neutral": true,
    "requires_plan": true,
    "schema": "leo-flow.steering-boundary.v1",
    "transport": "adapter_owned"
  },
  "subagent_plan": {
    "cost_policy": {
      "default_worker": "glm_max_worker",
      "direct_local_rule": "Do tiny tightly coupled edits directly when delegation setup and review would cost more than the edit.",
      "escalation": {
        "enter_planner_when": "hard_risk_or_receipt_backed_miss",
        "next_tier_requires": [
          "failure_class",
          "receipt_locator",
          "bounded_next_attempt"
        ],
        "order": [
          "glm_max_worker",
          "codex_luna_worker",
          "grok_max_worker",
          "cursor_worker",
          "codex_sol_worker",
          "planner_tier"
        ],
        "quota_fallback": "codex_terra_worker is selected only on a codex_sol_worker weekly-quota-limit receipt; otherwise Terra is off the ladder (Leo 2026-07-18: point Codex delegation at Sol instead of Terra).",
        "receipt_backed_miss_results": [
          "fail",
          "blocked",
          "auth_gap",
          "source_gap"
        ],
        "required_receipt_fields": [
          "source",
          "result",
          "claim",
          "ts"
        ],
        "retry_budget_per_tier": 1
      },
      "independent_review_worker": "grok_max_worker",
      "objective": "cost_per_completed_task",
      "owner": "leo-flow_compatibility",
      "policy": "Use the cheapest capable path, count retries and lead-review cost, and escalate only for a named hard boundary or a receipt-backed miss. Pilot owns the routing decision; Flow projects the compatibility schema; /delegate owns provider transport and private account selection.",
      "provider_quota": {
        "adapter": "/Users/leokwan/.ai/skills-active/delegate/scripts/provider-quota",
        "adapter_exit": 0,
        "cache": {
          "age_seconds": 0,
          "status": "hit",
          "ttl_seconds": 900
        },
        "measured_at": "2026-07-21T22:20:05Z",
        "providers": {
          "grok": {
            "contract": "installed_cli_internal",
            "period_start": "2026-07-18T11:22:08.274381Z",
            "remaining_percent": 90.0,
            "reset_at": "2026-07-25T11:22:08.274381Z",
            "source": "grok_build_billing_api",
            "status": "ok",
            "usage_percent": 10.0
          },
          "zai": {
            "accounts": [
              {
                "account": "account_1",
                "limits": {
                  "five_hour": {
                    "current_value": null,
                    "limit_value": null,
                    "remaining_percent": 65.0,
                    "reset_at": "2026-07-22T02:22:27.984000Z",
                    "usage_percent": 35.0
                  },
                  "monthly_tools": {
                    "current_value": 341,
                    "limit_value": 4000,
                    "remaining_percent": 92.0,
                    "reset_at": "2026-07-24T02:22:27.997000Z",
                    "usage_percent": 8.0
                  },
                  "weekly": {
                    "current_value": null,
                    "limit_value": null,
                    "remaining_percent": 99.0,
                    "reset_at": "2026-07-22T03:17:18.337000Z",
                    "usage_percent": 1.0
                  }
                },
                "status": "ok"
              },
              {
                "account": "account_2",
                "limits": {
                  "five_hour": {
                    "current_value": null,
                    "limit_value": null,
                    "remaining_percent": 100.0,
                    "reset_at": null,
                    "usage_percent": 0.0
                  },
                  "monthly_tools": {
                    "current_value": 0,
                    "limit_value": 4000,
                    "remaining_percent": 100.0,
                    "reset_at": "2026-07-25T07:23:38.979000Z",
                    "usage_percent": 0.0
                  },
                  "weekly": {
                    "current_value": null,
                    "limit_value": null,
                    "remaining_percent": 91.0,
                    "reset_at": "2026-07-23T07:23:38.997000Z",
                    "usage_percent": 9.0
                  }
                },
                "status": "ok"
              }
            ],
            "source": "zai_quota_api",
            "status": "ok"
          }
        },
        "routing": {
          "recommended_workers": [
            "glm_max_worker",
            "grok_max_worker"
          ],
          "rule": "prefer paid code workers with healthy coding quota; Z.ai monthly tools are excluded; capability and proof policy still apply",
          "worker_state": {
            "glm_max_worker": {
              "account_count": 2,
              "effective_remaining_percent": 91.0,
              "healthy_account_count": 2,
              "known_account_count": 2,
              "lowest_remaining_percent": 65.0,
              "quota_basis": "five_hour+weekly",
              "state": "prefer"
            },
            "grok_max_worker": {
              "effective_remaining_percent": 90.0,
              "lowest_remaining_percent": 90.0,
              "quota_basis": "billing_period",
              "state": "prefer"
            }
          }
        },
        "schema": "provider-quota.v1"
      },
      "provider_transport": "delegate/cost-route",
      "routing_owner": "pilot",
      "schema": "leo-flow.cost-policy.v1",
      "sol_ultra": {
        "auto_select": "never",
        "default": "disabled",
        "definition": "GPT-5.6 Sol with xhigh/ultra reasoning or an equivalent highest-cost Sol route.",
        "reason": "High cost and overthinking risk; no measured cost-per-completed-task advantage.",
        "reconsider_only_when": "The current user explicitly requests it, cheaper tiers have receipt-backed misses, and a verified adapter plus bounded budget exists."
      },
      "stop_reasoning": {
        "max_unproven_replans": 1,
        "next_step": "execute_or_collect_missing_receipt",
        "rule": "Stop planning when a deterministic gate settles the question or the first safe proofable move is named."
      },
      "usage_visibility": {
        "never_infer_quota_remaining": true,
        "portable_fields": [
          "input_tokens",
          "output_tokens",
          "cache_read_tokens",
          "cache_write_tokens",
          "context_tokens",
          "turns",
          "cost_usd",
          "quota_remaining",
          "quota_unit",
          "source",
          "measured_at"
        ],
        "unknown_value": null
      }
    },
    "delegation_policy": {
      "assignment_sink": "Write leader/follower assignment into FLOW.md, the owning PLAN.md claim/progress line, or the ledger; do not encode model routing in a second queue.",
      "mail_policy": "Mail: Superhuman Mail MCP only \u2014 never Gmail MCP (gmail__*, gmail-personal, gmail-fbl, raw ~/.gmail-mcp). Subagents included. If Superhuman is not set up, blocked_with_resume and set up Superhuman; do not fall back to Gmail.",
      "max_sidecars": 3,
      "no_overlap_rule": "Workers must own disjoint file sets; read-only scouts must not edit; writable workers edit only allowed_paths.",
      "single_plan_rule": "Every runner reads the same Authority Store, claims disjoint allowed_paths or read-only scope, writes receipts/foldback, and never creates a shadow queue.",
      "wait_rule": "Do not wait unless the next local action or merge/proof boundary is blocked on that answer."
    },
    "generated_at": "2026-07-21T22:20:05Z",
    "hours": 4.0,
    "lead": {
      "eligible_runners": [
        "codex_headless",
        "claude_code",
        "cursor_agent",
        "grok_build",
        "fable_planner"
      ],
      "id": "lead",
      "owner": "current agent",
      "rule": "The lead keeps coordination, safety, and acceptance local; Fable owns planner-tier work only when selected by a hard-boundary or receipt-backed escalation; Z.ai/GLM, Codex Luna, Grok, and Codex Sol writable followers may drive assigned disjoint implementation slices and fold back receipts before any merge/claim.",
      "selection": "Pick the runner with the best current tools, context, cost, and proof path for the mission; lead is a role, not a fixed hierarchy.",
      "task": "Run boot_safety locally, keep hard planning and acceptance on the planner/lead tier, and assign disjoint write-scoped slices to Z.ai/GLM or Codex Luna first; add bounded Grok critique or Cursor only when the task or a receipt-backed miss justifies it."
    },
    "leader_follower": {
      "assignment_sink": "Write leader/follower assignment into FLOW.md, the owning PLAN.md claim/progress line, or the ledger; do not encode model routing in a second queue.",
      "authority_boundary": "Vidux PLAN.md owns durable project state and Ledger owns append-only evidence; Pilot owns leader/follower orchestration, runner selection, scope assignment, foldback validation, and lead acceptance. Leo Flow preserves the compatibility schema.",
      "claude_lead": "Claude Code can drive when it owns the strongest live context or tool surface; Pilot still records assignment, claims, and proof foldback.",
      "codex_headless": "Codex can run headless as lead or sidecar; it must still read the Authority Store first and fold receipts back through Pilot.",
      "codex_native_rule": "Codex is a first-class lead: prefer its native worker/explorer collaboration lifecycle for eligible local work, not a shell-spawned Codex imitation. gpt-5.3-codex-spark never selects by default because it uses a separate usage class; only an explicit user request opens it.",
      "compatibility_implementation": "leo-flow",
      "driver_agnostic": "The driver seat is role-based, never brand-based (Leo 2026-07-18): Claude Code, Cursor, Grok Build, or headless Codex may lead per lead_selection. One harness, many models - model backends swap per task while the Authority Store, claims, and receipt foldback stay identical for every driver.",
      "escalation_rule": "Escalate only for a named hard boundary or a receipt-backed miss; one unproven re-plan is the limit before executing the first safe proofable move.",
      "follower_runners": [
        "codex_headless",
        "claude_code",
        "glm_max_worker",
        "codex_luna_worker",
        "grok_max_worker",
        "cursor_worker",
        "codex_sol_worker",
        "source_scout",
        "counter_review",
        "proof_audit"
      ],
      "host_native_rule": "When /pilot is loaded and eligible work has a useful disjoint, context-isolating, or independent-proof slice, the current host uses native subagents without waiting for a second delegation prompt. Maximum three followers, depth one; the lead inspects diffs, runs proof, folds receipts, and closes idle workers.",
      "lead_runners": [
        "codex_headless",
        "claude_code",
        "cursor_agent",
        "grok_build",
        "fable_planner"
      ],
      "lead_selection": "Pick the runner with the best current tools, context, cost, and proof path for the mission; lead is a role, not a fixed hierarchy.",
      "model_worker_default": "Safe non-trivial code defaults to bounded Z.ai/GLM implementation; use Codex Luna for a small first-party slice, Grok for bounded independent critique or an alternate, and Codex Sol for one hard well-bounded implementation slice after a receipt-backed miss (sole task doer - never orchestration); Codex Terra only on a Sol weekly-quota-limit receipt. Workers do not own planning or acceptance.",
      "owner": "pilot",
      "pilot_driver_contract": "skills/pilot/driver.json owns the portable host-native supervisory loop; this Flow contract remains the compatibility routing, scope, and receipt kernel.",
      "single_plan_rule": "Every runner reads the same Authority Store, claims disjoint allowed_paths or read-only scope, writes receipts/foldback, and never creates a shadow queue."
    },
    "mail_policy": "Mail: Superhuman Mail MCP only \u2014 never Gmail MCP (gmail__*, gmail-personal, gmail-fbl, raw ~/.gmail-mcp). Subagents included. If Superhuman is not set up, blocked_with_resume and set up Superhuman; do not fall back to Gmail.",
    "mutation_surface": "none",
    "next_action": "Start sidecars only after the lead has a non-overlapping local task.",
    "planning_tier": {
      "acceptance_owner": "current lead",
      "activation_gate": "explicit_request_or_receipt_backed_cheaper_tier_miss",
      "owner": "pilot",
      "planners": [
        {
          "activation": "explicit_request_or_receipt_backed_cheaper_tier_miss",
          "auto_select": false,
          "availability": "host_resolved",
          "binding": "host skill /fable (Claude/Fable planner tier)",
          "id": "fable",
          "role": "architecture_test_strategy_and_independent_review",
          "skill": "fable",
          "source_gap": null
        },
        {
          "activation": "redirect_to_codex_sol_worker",
          "auto_select": false,
          "availability": false,
          "binding": "workers: codex_sol_worker (first-party codex exec adapter, verified 2026-07-18)",
          "id": "sol",
          "role": "worker_only_never_orchestrator",
          "skill": "pilot",
          "source_gap": "sol_is_worker_tier_by_user_verdict"
        },
        {
          "activation": "disabled_by_cost_policy",
          "auto_select": false,
          "availability": false,
          "binding": null,
          "id": "sol_ultra",
          "role": "exceptional_last_resort_review_only",
          "skill": null,
          "source_gap": "sol_ultra_disabled_by_cost_policy"
        }
      ],
      "policy": "The current lead owns ordinary planning and final acceptance. Fable is an explicit or receipt-backed escalation for genuinely hard work; Z.ai/GLM and Grok are bounded implementation workers. Generic plan/planning or broad wording may recommend planning but never auto-spends a premium planner call.",
      "recommended": false,
      "requested": [
        "fable"
      ],
      "required": true,
      "selected": [
        "fable"
      ],
      "source_gaps": []
    },
    "projection_only": true,
    "quota_routing": {
      "alignment": "not_applicable",
      "applicable": false,
      "missing_recommended_workers": [],
      "projected_workers": [],
      "recommended_workers": [
        "glm_max_worker",
        "grok_max_worker"
      ]
    },
    "repo": "/Users/leokwan/Development/vidux-main-active",
    "request": "Design ABC to FIRE Vidux control plane with Claude Fable; read-only planning; fold draft into plans/abc-fire-control-plane",
    "roster": {
      "path": "/Users/leokwan/.ai/skills-active/pilot-leo/roster.yaml",
      "persona": "personal",
      "sha256": "a0e69d9b50cdb5b9197ae8544fffc2b94b50e5051f250321e097b2a35c7bd6c8"
    },
    "route": {
      "blocked_by_hard_walls": false,
      "code_intent_explicit": false,
      "hard_wall_hits": [],
      "lane_ids": [
        "voice"
      ],
      "proof_floors": {
        "voice": "current_artifact_or_diff_context"
      },
      "skills": [
        "crashcourse",
        "slop"
      ]
    },
    "schema": "leo-flow.subagents.v1",
    "sidecars": [
      {
        "agent_type": "evidence_gatherer",
        "allowed_paths": [],
        "branch": null,
        "command_hint": null,
        "context_paths": [],
        "context_sha256": {},
        "foldback_target": "FLOW.md",
        "follower_default": null,
        "id": "source_scout",
        "invocation_blocker": null,
        "invocation_branch": null,
        "invocation_git_common_dir": null,
        "invocation_head": null,
        "invocation_ready": false,
        "invocation_worktree": null,
        "lanes": [
          "snap",
          "queue",
          "review",
          "teach",
          "risk"
        ],
        "lead_eligible": null,
        "matched_hints": [],
        "matched_lanes": [],
        "mode": "research",
        "model_tier": null,
        "output": "cited_source_snapshot",
        "prompt": "Scope: source_scout for Leo Flow request 'Design ABC to FIRE Vidux control plane with Claude Fable; read-only planning; fold draft into plans/abc-fire-control-plane' in /Users/leokwan/Development/vidux-main-active. Mode: research. Lanes: snap, queue, review, teach, risk. Output: cited_source_snapshot. Skill: none. Model tier: n/a. Strength profile: n/a. Command hint: n/a. Receipt contract: sources, owners, open questions, and source_gap items only. Spawn contract: standard sidecar contract. Foldback target: FLOW.md. Write scope: none. Worktree: none. Branch: none. Allowed paths: none. Write blocker: none. Invocation ready: false. Read-only provider context: none. Mail: Superhuman Mail MCP only \u2014 never Gmail MCP (gmail__*, gmail-personal, gmail-fbl, raw ~/.gmail-mcp). Subagents included. If Superhuman is not set up, blocked_with_resume and set up Superhuman; do not fall back to Gmail. Only write inside the declared write scope; do not revert others' work; fold back to the parent/lead before any merge or claim; return concrete receipts, gaps, and next action.",
        "receipt_contract": "sources, owners, open questions, and source_gap items only.",
        "score": 4,
        "skill": null,
        "spawn_contract": null,
        "strength_profile": null,
        "wait": "Do not wait unless the next local action or merge/proof boundary is blocked on that answer.",
        "worktree": null,
        "write_blocker": null,
        "write_ready": false,
        "write_scope": "none"
      },
      {
        "agent_type": "pr_researcher",
        "allowed_paths": [],
        "branch": null,
        "command_hint": null,
        "context_paths": [],
        "context_sha256": {},
        "foldback_target": "FLOW.md",
        "follower_default": null,
        "id": "counter_review",
        "invocation_blocker": null,
        "invocation_branch": null,
        "invocation_git_common_dir": null,
        "invocation_head": null,
        "invocation_ready": false,
        "invocation_worktree": null,
        "lanes": [
          "review",
          "proof",
          "voice",
          "nurse"
        ],
        "lead_eligible": null,
        "matched_hints": [],
        "matched_lanes": [
          "voice"
        ],
        "mode": "research",
        "model_tier": null,
        "output": "stale_comment_or_major_risk_audit",
        "prompt": "Scope: counter_review for Leo Flow request 'Design ABC to FIRE Vidux control plane with Claude Fable; read-only planning; fold draft into plans/abc-fire-control-plane' in /Users/leokwan/Development/vidux-main-active. Mode: research. Lanes: voice. Output: stale_comment_or_major_risk_audit. Skill: none. Model tier: n/a. Strength profile: n/a. Command hint: n/a. Receipt contract: PR head/ref, file lines, review thread state, CI/check state, and residual risk. Spawn contract: standard sidecar contract. Foldback target: FLOW.md. Write scope: none. Worktree: none. Branch: none. Allowed paths: none. Write blocker: none. Invocation ready: false. Read-only provider context: none. Mail: Superhuman Mail MCP only \u2014 never Gmail MCP (gmail__*, gmail-personal, gmail-fbl, raw ~/.gmail-mcp). Subagents included. If Superhuman is not set up, blocked_with_resume and set up Superhuman; do not fall back to Gmail. Only write inside the declared write scope; do not revert others' work; fold back to the parent/lead before any merge or claim; return concrete receipts, gaps, and next action.",
        "receipt_contract": "PR head/ref, file lines, review thread state, CI/check state, and residual risk.",
        "score": 4,
        "skill": null,
        "spawn_contract": null,
        "strength_profile": null,
        "wait": "Do not wait unless the next local action or merge/proof boundary is blocked on that answer.",
        "worktree": null,
        "write_blocker": null,
        "write_ready": false,
        "write_scope": "none"
      },
      {
        "agent_type": "explorer",
        "allowed_paths": [],
        "branch": null,
        "command_hint": null,
        "context_paths": [],
        "context_sha256": {},
        "foldback_target": "FLOW.md",
        "follower_default": null,
        "id": "proof_audit",
        "invocation_blocker": null,
        "invocation_branch": null,
        "invocation_git_common_dir": null,
        "invocation_head": null,
        "invocation_ready": false,
        "invocation_worktree": null,
        "lanes": [
          "build",
          "proof",
          "ios",
          "music-backend"
        ],
        "lead_eligible": null,
        "matched_hints": [],
        "matched_lanes": [],
        "mode": "research",
        "model_tier": null,
        "output": "proof_gap_and_test_plan",
        "prompt": "Scope: proof_audit for Leo Flow request 'Design ABC to FIRE Vidux control plane with Claude Fable; read-only planning; fold draft into plans/abc-fire-control-plane' in /Users/leokwan/Development/vidux-main-active. Mode: research. Lanes: build, proof, ios, music-backend. Output: proof_gap_and_test_plan. Skill: none. Model tier: n/a. Strength profile: n/a. Command hint: n/a. Receipt contract: Exact commands, expected proof claim, skipped gates, and missing runtime/visual proof. Spawn contract: standard sidecar contract. Foldback target: FLOW.md. Write scope: none. Worktree: none. Branch: none. Allowed paths: none. Write blocker: none. Invocation ready: false. Read-only provider context: none. Mail: Superhuman Mail MCP only \u2014 never Gmail MCP (gmail__*, gmail-personal, gmail-fbl, raw ~/.gmail-mcp). Subagents included. If Superhuman is not set up, blocked_with_resume and set up Superhuman; do not fall back to Gmail. Only write inside the declared write scope; do not revert others' work; fold back to the parent/lead before any merge or claim; return concrete receipts, gaps, and next action.",
        "receipt_contract": "Exact commands, expected proof claim, skipped gates, and missing runtime/visual proof.",
        "score": 2,
        "skill": null,
        "spawn_contract": null,
        "strength_profile": null,
        "wait": "Do not wait unless the next local action or merge/proof boundary is blocked on that answer.",
        "worktree": null,
        "write_blocker": null,
        "write_ready": false,
        "write_scope": "none"
      }
    ],
    "stop_required": false,
    "weakest_proof_claim": "source_gap"
  },
  "updated_at": "2026-07-21T22:26:12Z"
}
```
