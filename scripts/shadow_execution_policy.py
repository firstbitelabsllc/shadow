#!/usr/bin/env python3
"""Small, explicit execution policy for Shadow's sealed native hosts.

This module chooses no host and reads no prompt.  A driving lead chooses the
host and one semantic work class; this policy resolves that pair to the native
model selector.  Account choice, credentials, quotas, and provider fallback
remain entirely inside each host CLI.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


POLICY_VERSION = "shadow.execution-policy.v2"
HOSTS = ("claude-code", "codex", "cursor", "grok", "zai", "codex-zai")
WORK_CLASSES = ("planning", "coding", "review", "lightweight")
DELEGATION_MODES = ("direct", "required")

_DELEGATION_CAPABILITIES = {
    "claude-code": "Agent",
    "codex": "multi_agent",
    "cursor": None,
    "grok": "spawn_subagent",
    "zai": None,
    "codex-zai": "multi_agent",
}


class ExecutionPolicyError(ValueError):
    """The requested host/work-class pair is not in the sealed policy."""


@dataclass(frozen=True)
class ExecutionRoute:
    host: str
    work_class: str
    model: str
    observed_model_pattern: str
    rationale: str

    def matches_observed_model(self, value: str | None) -> bool:
        return bool(value and re.fullmatch(self.observed_model_pattern, value, re.IGNORECASE))


def _route(
    host: str,
    work_class: str,
    model: str,
    observed: str,
    rationale: str,
) -> ExecutionRoute:
    return ExecutionRoute(host, work_class, model, observed, rationale)


_ROUTES = {
    # Claude Code exposes model aliases and reports the resolved model in its
    # stream-json init/result records.
    ("claude-code", "planning"): _route(
        "claude-code", "planning", "fable", r"claude-fable-5(?:\[1m\]|[-.].*)?", "hard planning"
    ),
    ("claude-code", "coding"): _route(
        "claude-code", "coding", "opus", r"claude-opus-5(?:\[1m\]|[-.].*)?", "hard implementation"
    ),
    ("claude-code", "review"): _route(
        "claude-code", "review", "fable", r"claude-fable-5(?:\[1m\]|[-.].*)?", "independent reasoning"
    ),
    ("claude-code", "lightweight"): _route(
        "claude-code", "lightweight", "sonnet", r"claude-sonnet-5(?:\[1m\]|[-.].*)?", "lower-cost native tier"
    ),
    # Codex emits the selected model and usage in native OTel trace spans.
    ("codex", "planning"): _route(
        "codex", "planning", "gpt-5.6-sol", r"gpt-5\.6-sol", "frontier planning"
    ),
    ("codex", "coding"): _route(
        "codex", "coding", "gpt-5.6-sol", r"gpt-5\.6-sol", "frontier implementation"
    ),
    ("codex", "review"): _route(
        "codex", "review", "gpt-5.6-terra", r"gpt-5\.6-terra", "cost-balanced independent review"
    ),
    ("codex", "lightweight"): _route(
        "codex", "lightweight", "gpt-5.6-luna", r"gpt-5\.6-luna", "efficient bounded work"
    ),
    # Cursor's live catalog supplies all four requested capability families.
    ("cursor", "planning"): _route(
        "cursor",
        "planning",
        "claude-fable-5-thinking-high",
        r"(?:claude-fable-5-thinking-high|claude fable 5 300k high)",
        "Cursor Fable planning",
    ),
    ("cursor", "coding"): _route(
        "cursor",
        "coding",
        "claude-opus-5-thinking-high",
        r"(?:claude-opus-5-thinking-high|claude opus 5 300k high)",
        "Cursor Opus implementation",
    ),
    ("cursor", "review"): _route(
        "cursor",
        "review",
        "cursor-grok-4.6-high",
        r"(?:cursor-grok-4\.6-high|cursor grok 4\.6 high)",
        "independent Cursor Grok review",
    ),
    ("cursor", "lightweight"): _route(
        "cursor",
        "lightweight",
        "Auto",
        r"Auto",
        "provider-managed lightweight lane; underlying model remains opaque",
    ),
    # Grok currently exposes only two models.  The policy says so instead of
    # fabricating a richer roster.
    ("grok", "planning"): _route(
        "grok", "planning", "grok-4.6", r"grok-4\.6(?:-build)?", "strongest available Grok tier"
    ),
    ("grok", "coding"): _route(
        "grok", "coding", "grok-4.6", r"grok-4\.6(?:-build)?", "strongest available Grok tier"
    ),
    ("grok", "review"): _route(
        "grok", "review", "grok-4.6", r"grok-4\.6(?:-build)?", "strongest available Grok tier"
    ),
    ("grok", "lightweight"): _route(
        "grok", "lightweight", "grok-4.5", r"grok-4\.5(?:-build)?", "only lower Grok tier exposed"
    ),
    # Z.AI currently exposes GLM-5.3-Flash as the volume coding lane. The
    # policy names that one model instead of inventing a richer roster.
    ("zai", "planning"): _route(
        "zai", "planning", "zai/glm-5.3-flash", r"zai/glm-5\.3-flash|glm-5\.3-flash", "GLM-5.3-Flash volume planning"
    ),
    ("zai", "coding"): _route(
        "zai", "coding", "zai/glm-5.3-flash", r"zai/glm-5\.3-flash|glm-5\.3-flash", "GLM-5.3-Flash volume implementation"
    ),
    ("zai", "review"): _route(
        "zai", "review", "zai/glm-5.3-flash", r"zai/glm-5\.3-flash|glm-5\.3-flash", "GLM-5.3-Flash volume review"
    ),
    ("zai", "lightweight"): _route(
        "zai", "lightweight", "zai/glm-5.3-flash", r"zai/glm-5\.3-flash|glm-5\.3-flash", "GLM-5.3-Flash volume lane"
    ),
    # codex-zai is the same Codex CLI on an isolated CODEX_HOME whose only
    # provider is Z.AI GLM-5.3-Flash. One volume model for every class; the
    # policy says so instead of inventing tiers the provider does not expose.
    ("codex-zai", "planning"): _route(
        "codex-zai", "planning", "glm-5.3-flash", r"glm-5\.3-flash", "GLM-5.3-Flash via Codex, volume planning"
    ),
    ("codex-zai", "coding"): _route(
        "codex-zai", "coding", "glm-5.3-flash", r"glm-5\.3-flash", "GLM-5.3-Flash via Codex, volume coding"
    ),
    ("codex-zai", "review"): _route(
        "codex-zai", "review", "glm-5.3-flash", r"glm-5\.3-flash", "GLM-5.3-Flash via Codex, volume review"
    ),
    ("codex-zai", "lightweight"): _route(
        "codex-zai", "lightweight", "glm-5.3-flash", r"glm-5\.3-flash", "GLM-5.3-Flash via Codex, volume lightweight"
    ),
}


def resolve_route(host: str, work_class: str) -> ExecutionRoute:
    if host not in HOSTS:
        raise ExecutionPolicyError(f"unsupported native host: {host}")
    if work_class not in WORK_CLASSES:
        raise ExecutionPolicyError(f"unsupported work class: {work_class}")
    try:
        return _ROUTES[(host, work_class)]
    except KeyError as exc:  # Defensive: every shipped pair is tested.
        raise ExecutionPolicyError(f"unsupported host/work-class pair: {host}/{work_class}") from exc


def native_model_argv(host: str, work_class: str) -> list[str]:
    route = resolve_route(host, work_class)
    return ["--model", route.model]


def delegation_capability(host: str, mode: str) -> str | None:
    if host not in HOSTS:
        raise ExecutionPolicyError(f"unsupported native host: {host}")
    if mode not in DELEGATION_MODES:
        raise ExecutionPolicyError(f"unsupported delegation mode: {mode}")
    capability = _DELEGATION_CAPABILITIES[host]
    if mode == "required" and capability is None:
        if host == "zai":
            raise ExecutionPolicyError(
                "zai has no verified structured native-child capability; "
                "wake when OpenCode exposes observable child lineage"
            )
        raise ExecutionPolicyError(
            "cursor has no verified structured native-child capability; "
            "wake when Cursor CLI exposes observable child lineage"
        )
    return capability if mode == "required" else None
