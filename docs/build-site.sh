#!/usr/bin/env bash
# Build the VitePress docs site (output: .vitepress/dist).
#
# The docs toolchain is npm's one sanctioned consumer in this repository: the
# 2026-08-09 ruling keeps the product itself on Git, Bash, and Python alone,
# and tests/test_browser_shell.py enforces that no tracked tooling under
# bin/, scripts/, or .github/ invokes npm or npx. This wrapper lives under
# docs/ precisely so that boundary stays visible and the product paths stay
# npm-free.
set -euo pipefail
cd "$(dirname "$0")"
npm ci
npm run docs:build:pages
