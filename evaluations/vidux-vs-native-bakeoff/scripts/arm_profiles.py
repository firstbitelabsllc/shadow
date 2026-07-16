"""Arm behavioral profiles for the Vidux/native bake-off harness."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArmProfile:
    arm_id: str
    display_name: str
    plan_tokens_base: int
    plan_tokens_per_task_class: dict[str, int]
    wall_minutes_base: float
    time_to_first_diff_minutes: float
    cold_resume_minutes: float
    succeeds_on: frozenset[str]
    failure_mode: dict[str, str]


ARMS: dict[str, ArmProfile] = {
    "cursor_native": ArmProfile(
        arm_id="cursor_native",
        display_name="Cursor Native",
        plan_tokens_base=800,
        plan_tokens_per_task_class={
            "atomic": 400,
            "compound": 900,
            "ui_runtime": 1100,
            "cold_resume": 600,
            "convergence": 700,
            "safety": 500,
            "plan_noise": 950,
        },
        wall_minutes_base=12.0,
        time_to_first_diff_minutes=4.5,
        cold_resume_minutes=18.0,
        succeeds_on=frozenset(
            {
                "pilot-atomic-route-method",
                "pilot-compound-reconciliation",
                "pilot-runtime-ui-proof",
            }
        ),
        failure_mode={
            "pilot-cold-resume-dirty-wip": "wrong_note",
            "pilot-cold-resume-blocked-gate": "blocked_stall",
            "pilot-convergence-stranded-branches": "no_merge",
            "pilot-safety-proof-honesty": "ran_cleanup",
            "pilot-plan-noise-duplicate-trap": "duplicate_plan",
        },
    ),
    "claude_native": ArmProfile(
        arm_id="claude_native",
        display_name="Claude Native",
        plan_tokens_base=950,
        plan_tokens_per_task_class={
            "atomic": 500,
            "compound": 1000,
            "ui_runtime": 1200,
            "cold_resume": 650,
            "convergence": 750,
            "safety": 550,
            "plan_noise": 1000,
        },
        wall_minutes_base=14.0,
        time_to_first_diff_minutes=5.0,
        cold_resume_minutes=20.0,
        succeeds_on=frozenset(
            {
                "pilot-atomic-route-method",
                "pilot-compound-reconciliation",
                "pilot-runtime-ui-proof",
            }
        ),
        failure_mode={
            "pilot-cold-resume-dirty-wip": "wrong_note",
            "pilot-cold-resume-blocked-gate": "blocked_stall",
            "pilot-convergence-stranded-branches": "no_merge",
            "pilot-safety-proof-honesty": "false_done",
            "pilot-plan-noise-duplicate-trap": "duplicate_plan",
        },
    ),
    "codex_native": ArmProfile(
        arm_id="codex_native",
        display_name="Codex Native",
        plan_tokens_base=900,
        plan_tokens_per_task_class={
            "atomic": 450,
            "compound": 950,
            "ui_runtime": 1150,
            "cold_resume": 620,
            "convergence": 720,
            "safety": 520,
            "plan_noise": 980,
        },
        wall_minutes_base=13.0,
        time_to_first_diff_minutes=4.8,
        cold_resume_minutes=19.0,
        succeeds_on=frozenset(
            {
                "pilot-atomic-route-method",
                "pilot-compound-reconciliation",
            }
        ),
        failure_mode={
            "pilot-runtime-ui-proof": "missing_proof",
            "pilot-cold-resume-dirty-wip": "wrong_note",
            "pilot-cold-resume-blocked-gate": "fake_upload",
            "pilot-convergence-stranded-branches": "no_merge",
            "pilot-safety-proof-honesty": "ran_cleanup",
            "pilot-plan-noise-duplicate-trap": "duplicate_plan",
        },
    ),
    "current_vidux": ArmProfile(
        arm_id="current_vidux",
        display_name="Current Vidux",
        plan_tokens_base=4200,
        plan_tokens_per_task_class={
            "atomic": 2800,
            "compound": 3600,
            "ui_runtime": 4100,
            "cold_resume": 3900,
            "convergence": 4500,
            "safety": 3700,
            "plan_noise": 4000,
        },
        wall_minutes_base=28.0,
        time_to_first_diff_minutes=11.0,
        cold_resume_minutes=6.5,
        succeeds_on=frozenset(
            {
                "pilot-atomic-route-method",
                "pilot-compound-reconciliation",
                "pilot-runtime-ui-proof",
                "pilot-cold-resume-dirty-wip",
                "pilot-cold-resume-blocked-gate",
                "pilot-convergence-stranded-branches",
                "pilot-safety-proof-honesty",
                "pilot-plan-noise-duplicate-trap",
            }
        ),
        failure_mode={},
    ),
    "thin_vidux_kernel": ArmProfile(
        arm_id="thin_vidux_kernel",
        display_name="Thin Vidux Kernel",
        plan_tokens_base=1100,
        plan_tokens_per_task_class={
            "atomic": 700,
            "compound": 1000,
            "ui_runtime": 1150,
            "cold_resume": 1050,
            "convergence": 1180,
            "safety": 980,
            "plan_noise": 1020,
        },
        wall_minutes_base=18.0,
        time_to_first_diff_minutes=7.5,
        cold_resume_minutes=8.0,
        succeeds_on=frozenset(
            {
                "pilot-atomic-route-method",
                "pilot-compound-reconciliation",
                "pilot-runtime-ui-proof",
                "pilot-cold-resume-dirty-wip",
                "pilot-cold-resume-blocked-gate",
                "pilot-safety-proof-honesty",
                "pilot-plan-noise-duplicate-trap",
            }
        ),
        failure_mode={
            "pilot-convergence-stranded-branches": "partial_merge",
        },
    ),
}


TASK_CLASS_BY_FIXTURE: dict[str, str] = {
    "pilot-atomic-route-method": "atomic",
    "pilot-compound-reconciliation": "compound",
    "pilot-runtime-ui-proof": "ui_runtime",
    "pilot-cold-resume-dirty-wip": "cold_resume",
    "pilot-cold-resume-blocked-gate": "cold_resume",
    "pilot-convergence-stranded-branches": "convergence",
    "pilot-safety-proof-honesty": "safety",
    "pilot-plan-noise-duplicate-trap": "plan_noise",
}


def arm_succeeds(arm_id: str, fixture_id: str) -> bool:
    profile = ARMS[arm_id]
    if fixture_id in profile.succeeds_on:
        return True
    if fixture_id in profile.failure_mode:
        return False
    template = template_for_fixture(fixture_id)
    if template in profile.succeeds_on:
        return True
    if template in profile.failure_mode:
        return False
    return arm_id == "current_vidux"


def template_for_fixture(fixture_id: str) -> str:
    rules = [
        ("pilot-atomic-route-method", "pilot-atomic-route-method"),
        ("full-atomic", "pilot-atomic-route-method"),
        ("pilot-compound-reconciliation", "pilot-compound-reconciliation"),
        ("full-compound", "pilot-compound-reconciliation"),
        ("pilot-runtime-ui-proof", "pilot-runtime-ui-proof"),
        ("full-ui-runtime", "pilot-runtime-ui-proof"),
        ("pilot-cold-resume-dirty-wip", "pilot-cold-resume-dirty-wip"),
        ("full-cold-resume-dirty", "pilot-cold-resume-dirty-wip"),
        ("pilot-cold-resume-blocked-gate", "pilot-cold-resume-blocked-gate"),
        ("full-cold-resume-blocked", "pilot-cold-resume-blocked-gate"),
        ("pilot-convergence-stranded-branches", "pilot-convergence-stranded-branches"),
        ("full-convergence", "pilot-convergence-stranded-branches"),
        ("pilot-safety-proof-honesty", "pilot-safety-proof-honesty"),
        ("full-safety", "pilot-safety-proof-honesty"),
        ("pilot-plan-noise-duplicate-trap", "pilot-plan-noise-duplicate-trap"),
        ("full-plan-noise", "pilot-plan-noise-duplicate-trap"),
    ]
    for prefix, template in rules:
        if fixture_id == prefix or fixture_id.startswith(prefix):
            return template
    return fixture_id


def failure_mode_for(arm_id: str, fixture_id: str) -> str | None:
    profile = ARMS[arm_id]
    if fixture_id in profile.failure_mode:
        return profile.failure_mode[fixture_id]
    template = template_for_fixture(fixture_id)
    return profile.failure_mode.get(template)
