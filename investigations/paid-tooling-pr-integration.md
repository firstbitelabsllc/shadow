# Paid Tooling → Vidux Draft-PR Integration

**Investigated:** 2026-04-11 (claude-opus-4-6). WebFetch + Nia MCP vs vendor docs.
**Scope:** Nia, Greptile, Sentry, Seer — wiring each into a vidux automation that pushes a branch and opens a draft PR.

Unresolved items are tagged `[UNVERIFIED]`. Everything else was confirmed against a vendor-authoritative URL on 2026-04-11.

---

## Recommended stack — who owns what lane

| Lane | Service | Why |
|---|---|---|
| Pre-push grounding (codex reads repo before writing) | **Nia** | Already wired as MCP; `nia_grep`/`search`/`tracer` give grounded context |
| Pre-merge **draft**-PR review | **Greptile** | Only service supporting drafts (`triggerOnDrafts`) + programmatic `trigger_code_review` MCP tool |
| Pre-merge deep bug prediction (human PRs only) | **Seer Code Review** | Skips drafts, so automation-only; good for Leo's manual work |
| Post-merge error feedback → next PLAN | **Sentry + `sentry-cli` release hooks** | Standard release-tracking loop; suspect-commit comments feed back to vidux |
| Post-error autonomous fix | **Seer Autofix** | Treat its generated PRs as an *inbound* lane on the vidux PLAN |

**Setup order:** Nia (done) → Sentry GitHub integration → `sentry-cli` in env → Greptile GitHub App + first-index wait → Seer toggle last (cost implication).

**Effort:** Nia S (formalize usage), Greptile M (App + `greptile.json`/repo + first-index + cap monitoring), Sentry S-M (CLI + release hooks + App), Seer S (UI toggle, but per-repo cost call), custom `/sentry` skill M.

---

## Order of operations (codex cron draft-PR flow)

```
read PLAN.md, pick next task
  → (pre-flight) nia_grep / nia search — verify no dup defs, gather context
  → edit code
  → git commit, git push origin <lane-branch>
  → gh pr create --draft ...
  → flip greptile.json triggerOnDrafts=true  OR  Greptile MCP trigger_code_review
  → wait ~3 min (Greptile review latency)
  → Greptile MCP list_merge_request_comments(addressed=false)
  → trivial comments: auto-fix, commit, push, mark addressed
  → non-trivial: log into PLAN as follow-up, leave PR draft
  → (post-merge cron) sentry-cli releases new/set-commits --auto/finalize
  → (next tick) Sentry MCP search_issues release:$VERSION → regression check
```

**Ship-today MVP:** Greptile App on `vidux` only → `greptile.json` (`triggerOnDrafts: true, strictness: 2`) → `GREPTILE_API_KEY` in `~/.zshrc` → Greptile MCP in `~/.claude.json` → wait 1-2h first index → test a draft PR → only then extend to Resplit + StrongYes + codex cron.

---

## 1. Nia (`trynia.ai`)

Research/search/indexing substrate, **not a PR bot**. No GitHub App, no webhooks, no PR comments. It is an *input* to a review flow (grounds Claude + Greptile's auto-fix loop), not an actor on the PR.

- **MCP:** production, already live for Leo. Remote HTTP `https://apigcp.trynia.ai/mcp` (bearer) or local stdio `pipx run --no-cache nia-mcp-server`.
- **PR-relevant tools:** `nia_grep`/`search` (ground claims vs indexed repo), `tracer` (live search, no indexing), `nia_package_search_hybrid` (verify third-party API shapes), `context` (persist findings).
- **CLI:** `bunx nia-wizard@latest` to install; `nia auth login [--api-key nk_...]`; `Authorization: Bearer <key>`. Env: `NIA_API_KEY`.
- **Min instrumentation:** set `NIA_API_KEY`, MCP in `~/.claude.json` (done), one `context` call at task end.

**Gotchas:** `nia_research(mode='deep')` hallucinates schemas (Leo's T14 incident) — use `quick` for URL discovery only, never paste its code into production. Rate-limited via `X-RateLimit-*`/`X-Monthly-Limit`, 429 on exceed. Pricing tiers `[UNVERIFIED]` (check app.trynia.ai).

---

## 2. Greptile (`greptile.com`)

Cloud PR review bot — owns the comment-on-draft-PR lane. **No standalone CLI**; consumed as an MCP server.

- **MCP install:** `claude mcp add --transport http greptile https://api.greptile.com/mcp --header "Authorization: Bearer $GREPTILE_API_KEY"`. Key from `app.greptile.com/settings/organization/api`. Env: `GREPTILE_API_KEY`.
- **MCP tools (PR subset):** `list_pull_requests`/`list_merge_requests`, `get_merge_request`, `list_merge_request_comments` (filter `addressed: bool`), `search_greptile_comments`, `list/get_code_review`, `trigger_code_review` (fire a review; needs repo + defaultBranch), `*_custom_context` (team standards / org memory).
- **What it does:** GitHub App auto-reviews PRs matching configured triggers within ~3 min; inline comments with severity (`strictness 1-3`); "Fix in X" button preloads Claude/Cursor/Devin. Default `triggerOnDrafts: false` — drafts skipped unless opted in. Manual trigger `@greptileai`; `skipReview: "AUTOMATIC"` keeps manual only.
- **Config:** `greptile.json` at repo root or `.greptile/` with cascading per-dir rules. Jira integration for ticket-aware reviews.
- **Min instrumentation:** install GitHub App per repo; `greptile.json` (`strictness: 2`, `triggerOnDrafts: true` for codex lane); `GREPTILE_API_KEY` in env.

**Gotchas:**
- Auto-fix's "requires an IDE" is UX not protocol — headless cron can call MCP tools + apply diffs directly; Greptile marks comments `addressed` when files change.
- First-time repo indexing is **1-2h** and blocks the first review. Resplit is large; enabling on Resplit + Vidux + StrongYes = up to 6h blocking — schedule overnight.
- **Pricing:** $30/seat/mo, 50 reviews included, $1/extra review; Genius API $0.45/request. A cron doing 10 PRs/day burns the 50 cap in 5 days — monitor. `[UNVERIFIED]` whether MCP `trigger_code_review` counts against the 50-review cap or against Genius API.
- Webhook/REST shape outside MCP `[UNVERIFIED]`.

---

## 3. Sentry (`sentry.io`)

Error monitoring + release/commit attribution. PR-adjacent piece: posts **post-deploy suspect-commit** comments — NOT a pre-merge gate (don't confuse with Seer Code Review).

- **CLI (`sentry-cli`):** `releases new "$VERSION"`, `releases set-commits "$VERSION" --auto` (suspect commits) or `--commit "owner/repo@sha"`, `releases finalize "$VERSION"`, `deploys new --release "$VERSION" -e <env>`, `sourcemaps upload`, `repos list`. Auth: `SENTRY_AUTH_TOKEN`.
- **MCP:** `claude mcp add --transport http sentry https://mcp.sentry.dev/mcp` (cloud, device-code OAuth) or `npx @sentry/mcp-server` (stdio, manual token scopes `org:read project:read event:write project:write`). Confirmed tools `search_events`, `search_issues`; full inventory `[UNVERIFIED]`.
- **GitHub integration** (separate from Seer): suspect-commit PR comments; `fixes SENTRY-ABC-123` auto-links resolution. Perms: Issues, Contents, PRs, Checks, Commit Statuses, Webhooks (R/W); Administration + Metadata (R); org Members (R).
- **Automation role:** post-merge feedback to next PLAN. After merge: `sentry-cli releases new $(git rev-parse HEAD)` → `set-commits --auto` → `finalize` → optional `deploys new -e production`. Next tick: Sentry MCP `search_issues` scoped `release:$VERSION` to detect regressions.

**Gotchas:** needs `SENTRY_AUTH_TOKEN` in env; MCP "production-ready but evolving, expect rough edges"; self-hosted = token auth, cloud = OAuth only.

---

## 4. Seer (`docs.sentry.io/product/ai-in-sentry/seer`)

Sentry's AI debugging agent. No dedicated CLI/MCP — accessed via the Sentry MCP's "Seer analysis access" (specific tool names `[UNVERIFIED]`). Two PR-facing features:

- **Autofix** (post-error): triggers on issue with 10+ events + high fixability + configured agent, or manually from issue page / Slack. Outputs root-cause + remediation; can **create new PRs** (possibly cross-repo) or checkout locally. PR creation can be disabled org-wide.
- **AI Code Review / Error Prediction** (pre-merge): triggers on PR opened (non-draft), draft→ready, or new commits to a ready PR. **Skips drafts entirely.** Manual trigger `@sentry review`. Outputs inline comments + GitHub status check. Perms: PRs (R/W), Checks (R/W). Enabling on a repo starts **"active contributor pricing."**

**Critical conflict:** Seer Code Review **will not run on drafts** — opposite of Greptile. If vidux opens drafts exclusively, Seer is silent until "Ready for review." Decision (recommended): drafts for the codex lane, real PRs for human-reviewed merges. Alternatives: post `@sentry review` to force a one-shot review on a draft, or skip Seer Code Review for automation lanes entirely.

**Autofix is an inbound lane:** it creates PRs in response to prod errors, not vidux plans. Open question — does the cron detect `seer/autofix-*` branches and promote them into PLAN.md tasks, or are they out-of-band?

**Gotchas:** drafts are a hard skip; paid add-on distinct from base Sentry ("active contributor pricing" per repo with Code Review on) — verify Leo has it active; GitHub-cloud only (no GHE self-hosted); Autofix PRs may span multiple repos.

---

## Open unknowns

1. **Greptile billing under automation** — do `trigger_code_review` MCP calls hit the 50/seat cap or the $0.45 Genius API? Email sales or test empirically on one repo.
2. **Sentry MCP full tool list** — connect via `claude mcp add` + `/mcp` to dump before building a `/sentry` skill.
3. **Seer Autofix inbound lane** — how does PLAN authority absorb Autofix-generated PRs (auto-promote `seer/autofix-*` branches vs out-of-band)?
4. **Nia pricing tiers** — fetch app.trynia.ai.
5. **Greptile webhook/REST shape outside MCP** — not on the MCP v2 docs index.
