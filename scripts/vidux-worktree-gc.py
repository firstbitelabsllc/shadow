#!/usr/bin/env python3
"""Classify and optionally remove safe Vidux automation worktrees.

Default mode is read-only. `--apply --yes` removes only clean, non-primary
worktrees whose branch is already merged into the base or whose PR is merged.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


SAFE_BUCKET = "merged_clean"
UNSAFE_BUCKETS = {"dirty", "open_pr", "closed_unmerged", "unmerged_no_pr", "unknown"}


class CommandError(RuntimeError):
    def __init__(self, command: List[str], returncode: int, stderr: str) -> None:
        self.command = command
        self.returncode = returncode
        self.stderr = stderr.strip()
        super().__init__(f"{' '.join(command)} exited {returncode}: {self.stderr}")


@dataclass
class PullRequestInfo:
    number: int
    state: str
    head_ref_name: str
    title: str
    is_draft: bool
    url: str
    merged_at: Optional[str]
    closed_at: Optional[str]


@dataclass
class WorktreeInfo:
    path: str
    branch: Optional[str]
    head: Optional[str]
    bucket: str
    dirty_files: int
    is_primary: bool
    in_base: bool
    removable: bool
    pr_number: Optional[int]
    pr_state: Optional[str]
    pr_url: Optional[str]
    reason: str


def run(command: List[str], cwd: Optional[Path] = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode != 0:
        raise CommandError(command, result.returncode, result.stderr)
    return result


def repo_root(repo: Path) -> Path:
    result = run(["git", "-C", str(repo), "rev-parse", "--show-toplevel"])
    return Path(result.stdout.strip()).resolve()


def parse_worktree_list(text: str) -> List[Dict[str, Any]]:
    worktrees: List[Dict[str, Any]] = []
    current: Dict[str, Any] = {}

    def flush() -> None:
        nonlocal current
        if current:
            worktrees.append(current)
            current = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            flush()
            continue
        key, _, value = line.partition(" ")
        if key == "worktree":
            flush()
            current["path"] = value
        elif key == "HEAD":
            current["head"] = value
        elif key == "branch":
            current["branch"] = short_branch(value)
        elif key == "detached":
            current["detached"] = True
        elif key == "bare":
            current["bare"] = True
    flush()
    return worktrees


def short_branch(ref: str) -> str:
    prefix = "refs/heads/"
    if ref.startswith(prefix):
        return ref[len(prefix) :]
    return ref


def load_worktrees(repo: Path) -> List[Dict[str, Any]]:
    result = run(["git", "-C", str(repo), "worktree", "list", "--porcelain"])
    return parse_worktree_list(result.stdout)


def dirty_file_count(path: Path) -> int:
    result = run(["git", "-C", str(path), "status", "--porcelain"], check=True)
    return len([line for line in result.stdout.splitlines() if line.strip()])


def is_ancestor(repo: Path, head: Optional[str], base: str) -> bool:
    if not head:
        return False
    result = run(["git", "-C", str(repo), "merge-base", "--is-ancestor", head, base], check=False)
    return result.returncode == 0


def load_prs(repo: Path, limit: int) -> Tuple[Dict[str, PullRequestInfo], Optional[str]]:
    command = [
        "gh",
        "pr",
        "list",
        "--state",
        "all",
        "--limit",
        str(limit),
        "--json",
        "number,state,title,headRefName,isDraft,url,mergedAt,closedAt",
    ]
    result = run(command, cwd=repo, check=False)
    if result.returncode != 0:
        return {}, result.stderr.strip() or "gh pr list failed"

    try:
        raw_prs = json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        return {}, f"could not parse gh pr list JSON: {exc}"

    prs_by_branch: Dict[str, List[PullRequestInfo]] = {}
    for raw in raw_prs:
        head_ref = raw.get("headRefName") or ""
        if not head_ref:
            continue
        pr = PullRequestInfo(
            number=int(raw.get("number") or 0),
            state=str(raw.get("state") or "").upper(),
            head_ref_name=head_ref,
            title=str(raw.get("title") or ""),
            is_draft=bool(raw.get("isDraft")),
            url=str(raw.get("url") or ""),
            merged_at=raw.get("mergedAt"),
            closed_at=raw.get("closedAt"),
        )
        prs_by_branch.setdefault(head_ref, []).append(pr)

    priority = {"OPEN": 0, "MERGED": 1, "CLOSED": 2}
    selected: Dict[str, PullRequestInfo] = {}
    for branch, prs in prs_by_branch.items():
        prs.sort(key=lambda pr: (priority.get(pr.state, 9), -pr.number))
        selected[branch] = prs[0]
    return selected, None


def classify_worktree(
    repo: Path,
    raw: Dict[str, Any],
    primary_path: Path,
    prs_by_branch: Dict[str, PullRequestInfo],
    base: str,
    warnings: List[str],
) -> WorktreeInfo:
    path = Path(raw["path"]).resolve()
    branch = raw.get("branch")
    head = raw.get("head")
    is_primary = path == primary_path

    try:
        dirty_count = dirty_file_count(path)
    except CommandError as exc:
        warnings.append(f"could not read status for {path}: {exc.stderr}")
        dirty_count = -1

    in_base = is_ancestor(repo, head, base)
    pr = prs_by_branch.get(branch or "")

    bucket = "unknown"
    reason = "could not classify"

    if is_primary:
        bucket = "primary"
        reason = "primary checkout is never removed"
    elif dirty_count < 0:
        bucket = "unknown"
        reason = "git status failed"
    elif dirty_count > 0:
        bucket = "dirty"
        reason = f"{dirty_count} uncommitted file(s)"
    elif pr and pr.state == "OPEN":
        bucket = "open_pr"
        reason = f"open PR #{pr.number}"
    elif pr and pr.state == "MERGED":
        bucket = SAFE_BUCKET
        reason = f"merged PR #{pr.number}"
    elif in_base:
        bucket = SAFE_BUCKET
        reason = f"HEAD is contained in {base}"
    elif pr and pr.state == "CLOSED":
        bucket = "closed_unmerged"
        reason = f"closed unmerged PR #{pr.number}"
    elif branch:
        bucket = "unmerged_no_pr"
        reason = "branch has commits not in base and no PR"

    removable = bucket == SAFE_BUCKET and not is_primary and dirty_count == 0
    return WorktreeInfo(
        path=str(path),
        branch=branch,
        head=head,
        bucket=bucket,
        dirty_files=dirty_count,
        is_primary=is_primary,
        in_base=in_base,
        removable=removable,
        pr_number=pr.number if pr else None,
        pr_state=pr.state if pr else None,
        pr_url=pr.url if pr else None,
        reason=reason,
    )


def summarize(worktrees: Iterable[WorktreeInfo]) -> Dict[str, int]:
    summary: Dict[str, int] = {}
    for worktree in worktrees:
        summary[worktree.bucket] = summary.get(worktree.bucket, 0) + 1
    summary["total"] = sum(summary.values())
    summary["removable"] = sum(1 for worktree in worktrees if worktree.removable)
    return summary


def format_text(repo: Path, base: str, worktrees: List[WorktreeInfo], warnings: List[str]) -> str:
    summary = summarize(worktrees)
    lines = [
        f"vidux-worktree-gc: {repo}",
        f"base: {base}",
        "summary: "
        + ", ".join(f"{key}={summary[key]}" for key in sorted(summary.keys()) if key != "total")
        + f", total={summary.get('total', 0)}",
    ]

    if warnings:
        lines.append("")
        lines.append("warnings:")
        for warning in warnings:
            lines.append(f"  - {warning}")

    lines.append("")
    lines.append("worktrees:")
    for worktree in sorted(worktrees, key=lambda item: (item.bucket, item.path)):
        branch = worktree.branch or "(detached)"
        pr = f" PR#{worktree.pr_number}" if worktree.pr_number else ""
        marker = " removable" if worktree.removable else ""
        lines.append(f"  - [{worktree.bucket}{marker}] {branch}{pr} :: {worktree.path}")
        lines.append(f"    {worktree.reason}")

    if summary.get("removable", 0):
        lines.append("")
        lines.append("to remove safe local worktrees:")
        lines.append(f"  python3 scripts/vidux-worktree-gc.py --base {base} --apply --yes")
    return "\n".join(lines)


def remove_worktrees(repo: Path, worktrees: List[WorktreeInfo], delete_branches: bool) -> List[str]:
    removed: List[str] = []
    for worktree in worktrees:
        if not worktree.removable:
            continue
        run(["git", "-C", str(repo), "worktree", "remove", worktree.path])
        removed.append(worktree.path)
        if delete_branches and worktree.branch:
            run(["git", "-C", str(repo), "branch", "-d", worktree.branch], check=False)
    return removed


def build_payload(
    repo: Path,
    base: str,
    worktrees: List[WorktreeInfo],
    warnings: List[str],
    removed: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "repo": str(repo),
        "base": base,
        "summary": summarize(worktrees),
        "warnings": warnings,
        "removed": removed or [],
        "worktrees": [asdict(worktree) for worktree in worktrees],
    }


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", nargs="?", default=".", help="Repository or worktree path to inspect.")
    parser.add_argument("--base", default="origin/main", help="Base ref used to detect already-merged commits.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--apply", action="store_true", help="Remove only safe merged_clean worktrees.")
    parser.add_argument("--yes", action="store_true", help="Required with --apply.")
    parser.add_argument(
        "--delete-branches",
        action="store_true",
        help="After removing safe worktrees, run git branch -d for their local branches.",
    )
    parser.add_argument("--pr-limit", type=int, default=300, help="Maximum PRs to load from gh.")
    parser.add_argument("--gate", action="store_true", help="Exit 2 when the worktree count exceeds --max-worktrees.")
    parser.add_argument("--max-worktrees", type=int, default=None, help="Gate threshold for total worktrees.")
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    if args.apply and not args.yes:
        print("--apply requires --yes", file=sys.stderr)
        return 1

    repo = repo_root(Path(args.repo))
    warnings: List[str] = []
    raw_worktrees = load_worktrees(repo)
    if not raw_worktrees:
        print("no worktrees found", file=sys.stderr)
        return 1

    primary_path = Path(raw_worktrees[0]["path"]).resolve()
    prs_by_branch, pr_warning = load_prs(repo, args.pr_limit)
    if pr_warning:
        warnings.append(pr_warning)

    worktrees = [
        classify_worktree(repo, raw, primary_path, prs_by_branch, args.base, warnings)
        for raw in raw_worktrees
    ]

    removed: List[str] = []
    if args.apply:
        removed = remove_worktrees(repo, worktrees, args.delete_branches)
        if removed:
            raw_worktrees = load_worktrees(repo)
            worktrees = [
                classify_worktree(repo, raw, primary_path, prs_by_branch, args.base, warnings)
                for raw in raw_worktrees
            ]

    payload = build_payload(repo, args.base, worktrees, warnings, removed)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(format_text(repo, args.base, worktrees, warnings))
        if removed:
            print("")
            print("removed:")
            for path in removed:
                print(f"  - {path}")

    if args.gate and args.max_worktrees is not None and payload["summary"]["total"] > args.max_worktrees:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
