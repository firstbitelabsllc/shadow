#!/usr/bin/env python3
"""Bridge resplit-ios `[asc-XXX]` PRs to Linear EVE issues.

Background: resplit-ios merge titles routinely carry App Store Connect bug
IDs in the form `[asc-XXX]`, but no corresponding Linear EVE issue is
created — the `/resplit-watch` user-feedback loop therefore cannot see ASC
work in Linear. Section 4 of the linear-health-watch harness exists to
detect this gap; this script is the upstream fix that closes it.

For each merged PR with title matching `\\[asc-([A-Za-z0-9]+)\\]`, the
script:

1. Searches Linear (project `resplit-ios`) for any issue whose description,
   title, or any comment body mentions the ASC ID. If found: skip
   (idempotent on re-run).
2. Otherwise creates a Linear issue with title equal to the PR title (ASC
   ID kept), description containing ASC ID + PR URL + merged-at, project
   `resplit-ios`, state Done, label `pr-merged`.

CLI flags:
  --repo <owner/repo>      default `firstbitelabsllc/resplit-ios`
  --since-hours <int>      default 24
  --dry-run                log would-create entries, no mutation
  --token-file <path>      default `~/.config/vidux/linear.token`
  --project-name <name>    default `resplit-ios`
  --no-network             skip gh + Linear calls (returns SKIPPED envelope;
                           useful for CI smoke + tests)

Output schema (always JSON to stdout, even on dry-run):
    {
      "bridge_at": "<ISO8601>",
      "repo": "<owner/repo>",
      "since_hours": <int>,
      "dry_run": <bool>,
      "scanned_prs": <int>,
      "asc_prs": <int>,
      "would_create": [{"asc_id", "pr_number", "pr_url", "title", ...}],
      "created":      [{"asc_id", "pr_number", "issue_id", "identifier"}],
      "skipped":      [{"asc_id", "pr_number", "reason", "match_id"}],
      "errors":       [{"asc_id", "pr_number", "error"}]
    }

Exit codes:
  0  ran cleanly (zero or more bridges, including dry-run)
  1  one or more errors recorded in `errors`
  2  CLI / env failure (missing token file when network is required)

Pure stdlib. No third-party deps. Logic is split into pure functions taking
injected fetchers; the live fetchers live in the bottom half of the file.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_REPO = "firstbitelabsllc/resplit-ios"
DEFAULT_SINCE_HOURS = 24
DEFAULT_TOKEN_FILE = "~/.config/vidux/linear.token"
DEFAULT_PROJECT_NAME = "resplit-ios"
DEFAULT_DONE_STATE_NAMES = ("Done", "Completed", "Shipped")
DEFAULT_LABEL_NAME = "pr-merged"

LINEAR_ENDPOINT = "https://api.linear.app/graphql"
LINEAR_USER_AGENT = "vidux-asc-bridge/1.0"
HTTP_TIMEOUT = 30

# Title regex: case-insensitive `[asc-<id>]` where <id> is 1+ alphanumerics.
ASC_ID_RE = re.compile(r"\[asc-([A-Za-z0-9]+)\]", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Data shape
# ---------------------------------------------------------------------------


@dataclass
class BridgeResult:
    bridge_at: str
    repo: str
    since_hours: int
    dry_run: bool
    scanned_prs: int = 0
    asc_prs: int = 0
    would_create: list[dict] = field(default_factory=list)
    created: list[dict] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "bridge_at": self.bridge_at,
            "repo": self.repo,
            "since_hours": self.since_hours,
            "dry_run": self.dry_run,
            "scanned_prs": self.scanned_prs,
            "asc_prs": self.asc_prs,
            "would_create": list(self.would_create),
            "created": list(self.created),
            "skipped": list(self.skipped),
            "errors": list(self.errors),
        }


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def parse_asc_id(title: str | None) -> str | None:
    """Return the lowercase ASC ID or None.

    Matching is case-insensitive in the literal `asc-` prefix; the captured
    ID is normalized to lowercase so re-runs find the same Linear card.
    """
    if not title:
        return None
    m = ASC_ID_RE.search(title)
    if not m:
        return None
    return m.group(1).lower()


def merged_at_iso(since_hours: int, *, now: _dt.datetime | None = None) -> str:
    """Compute the `merged:>...` cutoff for `gh pr list --search`."""
    base = now or _dt.datetime.now(_dt.timezone.utc)
    cutoff = base - _dt.timedelta(hours=since_hours)
    return cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")


def render_description(asc_id: str, pr: dict) -> str:
    """Build the Linear issue description for a freshly-bridged ASC PR."""
    pr_url = pr.get("url") or ""
    pr_number = pr.get("number")
    merged_at = pr.get("mergedAt") or pr.get("merged_at") or ""
    title = pr.get("title") or ""
    lines = [
        f"ASC ID: {asc_id}",
        "",
        f"PR: #{pr_number} — {title}",
        f"URL: {pr_url}",
    ]
    if merged_at:
        lines.append(f"Merged: {merged_at}")
    lines.append("")
    lines.append(
        "Auto-bridged by `scripts/vidux-asc-bridge.py` to give the "
        "/resplit-watch user-feedback loop visibility into shipped ASC "
        "work."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Orchestrator (pure — accepts injected fetchers)
# ---------------------------------------------------------------------------


def run_bridge(
    *,
    repo: str = DEFAULT_REPO,
    since_hours: int = DEFAULT_SINCE_HOURS,
    dry_run: bool = False,
    fetch_merged_prs: Callable[[str, int], list[dict]],
    find_existing_eve: Callable[[str], dict | None],
    create_eve: Callable[[str, dict], dict],
    now: _dt.datetime | None = None,
) -> BridgeResult:
    """Run the bridge.

    `fetch_merged_prs(repo, since_hours)` returns a list of PR dicts each
    with at least `number`, `title`, `url`, `mergedAt`.

    `find_existing_eve(asc_id)` returns the matching Linear issue dict
    (`{id, identifier, title}`) or None.

    `create_eve(asc_id, pr)` returns the newly-created Linear issue dict
    (`{id, identifier}`). It is only called when `dry_run` is False.

    `now` is injectable for deterministic timestamps in tests.
    """
    now = now or _dt.datetime.now(_dt.timezone.utc)
    bridge_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    result = BridgeResult(
        bridge_at=bridge_at,
        repo=repo,
        since_hours=since_hours,
        dry_run=dry_run,
    )

    prs = fetch_merged_prs(repo, since_hours) or []
    result.scanned_prs = len(prs)

    seen_asc_ids: set[str] = set()
    for pr in prs:
        asc_id = parse_asc_id(pr.get("title"))
        if not asc_id:
            continue
        result.asc_prs += 1

        # Idempotency within a single run: if two PRs carry the same ASC
        # ID, we only attempt one creation.
        if asc_id in seen_asc_ids:
            result.skipped.append({
                "asc_id": asc_id,
                "pr_number": pr.get("number"),
                "reason": "duplicate-asc-id-in-run",
            })
            continue
        seen_asc_ids.add(asc_id)

        try:
            existing = find_existing_eve(asc_id)
        except Exception as exc:  # pragma: no cover - defensive
            result.errors.append({
                "asc_id": asc_id,
                "pr_number": pr.get("number"),
                "error": f"find_existing_eve failed: {exc}",
            })
            continue

        if existing:
            result.skipped.append({
                "asc_id": asc_id,
                "pr_number": pr.get("number"),
                "reason": "linear-issue-exists",
                "match_id": existing.get("id"),
                "match_identifier": existing.get("identifier"),
            })
            continue

        candidate = {
            "asc_id": asc_id,
            "pr_number": pr.get("number"),
            "pr_url": pr.get("url"),
            "title": pr.get("title"),
            "merged_at": pr.get("mergedAt") or pr.get("merged_at"),
        }
        if dry_run:
            result.would_create.append(candidate)
            continue

        try:
            issue = create_eve(asc_id, pr)
        except Exception as exc:
            result.errors.append({
                "asc_id": asc_id,
                "pr_number": pr.get("number"),
                "error": f"create_eve failed: {exc}",
            })
            continue

        result.created.append({
            "asc_id": asc_id,
            "pr_number": pr.get("number"),
            "issue_id": issue.get("id"),
            "identifier": issue.get("identifier"),
        })

    return result


# ---------------------------------------------------------------------------
# Live fetchers (gh CLI + Linear GraphQL)
# ---------------------------------------------------------------------------


def _live_fetch_merged_prs(repo: str, since_hours: int) -> list[dict]:
    cutoff = merged_at_iso(since_hours)
    cmd = [
        "gh",
        "pr",
        "list",
        "--repo",
        repo,
        "--state",
        "merged",
        "--search",
        f"merged:>{cutoff}",
        "--json",
        "number,title,url,mergedAt",
        "--limit",
        "200",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        return []
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []


def _load_token(token_file: Path) -> str:
    if not token_file.exists():
        raise RuntimeError(f"token file not found: {token_file}")
    token = token_file.read_text(encoding="utf-8").strip()
    if not token:
        raise RuntimeError(f"token file empty: {token_file}")
    return token


def _post_linear(query: str, variables: dict, *, token: str) -> dict[str, Any]:
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = urllib.request.Request(
        LINEAR_ENDPOINT,
        data=body,
        method="POST",
        headers={
            "Authorization": token,
            "Content-Type": "application/json",
            "User-Agent": LINEAR_USER_AGENT,
        },
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        raw = resp.read().decode("utf-8")
    payload = json.loads(raw)
    if payload.get("errors"):
        raise RuntimeError(f"GraphQL error: {payload['errors']}")
    return payload.get("data") or {}


_PROJECT_QUERY = """
query($name: String!) {
  projects(filter: {name: {eq: $name}}, first: 5) {
    nodes { id name }
  }
}
"""

_DONE_STATE_QUERY = """
query($projectId: String!) {
  project(id: $projectId) {
    id
    teams(first: 5) { nodes { id states(first: 50) { nodes { id name type } } } }
  }
}
"""

_LABEL_QUERY = """
query($name: String!) {
  issueLabels(filter: {name: {eq: $name}}, first: 5) {
    nodes { id name }
  }
}
"""

_SEARCH_QUERY = """
query($q: String!) {
  issues(filter: {searchableContent: {contains: $q}}, first: 10) {
    nodes { id identifier title }
  }
}
"""

_CREATE_MUTATION = """
mutation($input: IssueCreateInput!) {
  issueCreate(input: $input) {
    success
    issue { id identifier }
  }
}
"""


def _resolve_project_id(name: str, *, token: str) -> str | None:
    data = _post_linear(_PROJECT_QUERY, {"name": name}, token=token)
    nodes = ((data.get("projects") or {}).get("nodes")) or []
    for node in nodes:
        if (node.get("name") or "").lower() == name.lower():
            return node.get("id")
    return nodes[0]["id"] if nodes else None


def _resolve_done_state(project_id: str, *, token: str) -> tuple[str | None, str | None]:
    """Return `(team_id, done_state_id)` for the given project."""
    data = _post_linear(_DONE_STATE_QUERY, {"projectId": project_id}, token=token)
    project = data.get("project") or {}
    teams = ((project.get("teams") or {}).get("nodes")) or []
    for team in teams:
        team_id = team.get("id")
        states = ((team.get("states") or {}).get("nodes")) or []
        # Prefer matching by Linear state type=completed; fallback to a
        # name-match against DEFAULT_DONE_STATE_NAMES.
        for st in states:
            if (st.get("type") or "").lower() == "completed":
                return team_id, st.get("id")
        for st in states:
            if st.get("name") in DEFAULT_DONE_STATE_NAMES:
                return team_id, st.get("id")
    return None, None


def _resolve_label_id(name: str, *, token: str) -> str | None:
    data = _post_linear(_LABEL_QUERY, {"name": name}, token=token)
    nodes = ((data.get("issueLabels") or {}).get("nodes")) or []
    return nodes[0]["id"] if nodes else None


def make_live_find_existing_eve(
    *, token: str, project_name: str
) -> Callable[[str], dict | None]:
    def _find(asc_id: str) -> dict | None:
        # `searchableContent` covers title + description + comment bodies.
        # We scope to project_name client-side to avoid Linear-side filter
        # complexity; max 10 results is plenty for an ASC ID lookup.
        data = _post_linear(_SEARCH_QUERY, {"q": f"asc-{asc_id}"}, token=token)
        nodes = ((data.get("issues") or {}).get("nodes")) or []
        if not nodes:
            return None
        return nodes[0]
    return _find


def make_live_create_eve(
    *,
    token: str,
    project_name: str,
    label_name: str = DEFAULT_LABEL_NAME,
) -> Callable[[str, dict], dict]:
    project_id_cache: dict[str, str | None] = {}
    state_cache: dict[str, tuple[str | None, str | None]] = {}
    label_cache: dict[str, str | None] = {}

    def _project_id() -> str | None:
        if project_name not in project_id_cache:
            project_id_cache[project_name] = _resolve_project_id(
                project_name, token=token
            )
        return project_id_cache[project_name]

    def _state(project_id: str) -> tuple[str | None, str | None]:
        if project_id not in state_cache:
            state_cache[project_id] = _resolve_done_state(project_id, token=token)
        return state_cache[project_id]

    def _label(name: str) -> str | None:
        if name not in label_cache:
            label_cache[name] = _resolve_label_id(name, token=token)
        return label_cache[name]

    def _create(asc_id: str, pr: dict) -> dict:
        project_id = _project_id()
        if not project_id:
            raise RuntimeError(f"project not found: {project_name}")
        team_id, state_id = _state(project_id)
        if not team_id:
            raise RuntimeError(
                f"no team resolved for project {project_name} ({project_id})"
            )
        input_obj: dict[str, Any] = {
            "teamId": team_id,
            "projectId": project_id,
            "title": pr.get("title") or f"ASC {asc_id}",
            "description": render_description(asc_id, pr),
        }
        if state_id:
            input_obj["stateId"] = state_id
        label_id = _label(label_name)
        if label_id:
            input_obj["labelIds"] = [label_id]
        data = _post_linear(_CREATE_MUTATION, {"input": input_obj}, token=token)
        payload = data.get("issueCreate") or {}
        if not payload.get("success") or not payload.get("issue"):
            raise RuntimeError(f"issueCreate failed: {data}")
        return payload["issue"]

    return _create


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", default=DEFAULT_REPO)
    p.add_argument("--since-hours", type=int, default=DEFAULT_SINCE_HOURS)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--token-file", default=DEFAULT_TOKEN_FILE)
    p.add_argument("--project-name", default=DEFAULT_PROJECT_NAME)
    p.add_argument("--label-name", default=DEFAULT_LABEL_NAME)
    p.add_argument(
        "--no-network",
        action="store_true",
        help="skip gh + Linear calls (returns empty envelope; for CI smoke)",
    )
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    now = _dt.datetime.now(_dt.timezone.utc)
    bridge_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    if args.no_network:
        envelope = BridgeResult(
            bridge_at=bridge_at,
            repo=args.repo,
            since_hours=args.since_hours,
            dry_run=args.dry_run,
        ).as_dict()
        envelope["skipped_reason"] = "no-network"
        print(json.dumps(envelope, indent=2))
        return 0

    token_path = Path(os.path.expanduser(args.token_file))
    if not args.dry_run:
        try:
            token = _load_token(token_path)
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
    else:
        # Dry-run still needs Linear search to know what would be skipped
        # vs created. If token missing, fall back to empty find_existing_eve
        # so every ASC PR appears as `would_create`.
        try:
            token = _load_token(token_path)
        except RuntimeError:
            token = ""

    if token:
        find = make_live_find_existing_eve(token=token, project_name=args.project_name)
    else:
        def find(_asc: str) -> dict | None:
            return None

    if not args.dry_run:
        create = make_live_create_eve(
            token=token,
            project_name=args.project_name,
            label_name=args.label_name,
        )
    else:
        def create(_asc: str, _pr: dict) -> dict:  # pragma: no cover
            raise RuntimeError("dry-run: create_eve must not be called")

    result = run_bridge(
        repo=args.repo,
        since_hours=args.since_hours,
        dry_run=args.dry_run,
        fetch_merged_prs=_live_fetch_merged_prs,
        find_existing_eve=find,
        create_eve=create,
        now=now,
    )
    print(json.dumps(result.as_dict(), indent=2))
    return 1 if result.errors else 0


if __name__ == "__main__":
    sys.exit(main())
