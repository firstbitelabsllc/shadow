#!/usr/bin/env bash
set -euo pipefail
REPO_DIR="${1:?repo dir required}"
OUT_DIR="${2:?output dir required}"
mkdir -p "$OUT_DIR"
cd "$REPO_DIR"
git status --porcelain=v1 > "$OUT_DIR/git-status.txt" 2>&1 || true
git diff > "$OUT_DIR/git-diff.patch" 2>&1 || true
git branch -a > "$OUT_DIR/git-branches.txt" 2>&1 || true
find . -type f ! -path './.git/*' | sort > "$OUT_DIR/file-list.txt"
if [ -f checks/visible_check.py ]; then
  python3 checks/visible_check.py > "$OUT_DIR/visible-check.txt" 2>&1 || echo "rc=$?" >> "$OUT_DIR/visible-check.txt"
fi
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$OUT_DIR/captured-at.txt"
