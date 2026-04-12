# Paid Tooling → Vidux Draft-PR Integration

**Investigator:** claude-opus-4-6 (general-purpose subagent)
**Date:** 2026-04-11
**Scope:** Nia, Greptile, Sentry, Seer — how to wire each into a vidux automation that pushes a branch and opens a draft PR.
**Methodology:** WebFetch against vendor docs + Nia MCP bridge. Unverified claims marked `[UNVERIFIED]`. No nia-deep synthesized code was copied.

---

## Legend

- `[V]` = verified against vendor-authoritative URL in this session
- `[UNVERIFIED]` = claim we could not confirm; treat as hypothesis
- All URLs in the "Sources" column were fetched live on 2026-04-11

---

## 1. Nia (`trynia.ai`)

**One-line role:** Research/search/indexing substrate. NOT a PR bot. Nia is what *other* agents (Claude, the vidux automation itself) call during a review to get grounded context.

### 1.1 CLI surface

| Item | Value | Source |
|---|---|---|
| Install (one-shot) | `bunx nia-wizard@latest` (also `npx`, `pnpx`, `yarn dlx`) [V] | docs.trynia.ai/integrations/installation/cli.md |
| Auth | `nia auth login` (interactive) or `nia auth login --api-key "nk_..."` [V] | same |
| Auth storage | API key in env or secrets manager; `Authorization: Bearer <key>` header [V] | docs.trynia.ai/api-guide |
| Primary subcommands | `nia repos index/read/grep/tree`, `nia sources index`, `nia search query/universal/web/deep`, `nia oracle job/stream/status`, `nia tracer run`, `nia contexts save`, `nia packages grep`, `nia github tree/read/search/glob`, `nia usage` [V] | docs.trynia.ai/integrations/installation/cli.md |
| Global flags | `--api-key`, `--verbose`, `--no-color` [V] | same |

### 1.2 MCP server

| Item | Value | Source |
|---|---|---|
| Exists? | **Yes, production.** [V] | docs.trynia.ai/integrations/installation/mcp.md |
| Transport | Remote HTTP (recommended) `https://apigcp.trynia.ai/mcp` with bearer token, OR local stdio via `pipx run --no-cache nia-mcp-server` [V] | same |
| Tools (confirmed available in current Claude Code session) | `mcp__nia__index`, `search`, `manage_resource`, `nia_read`, `nia_grep`, `nia_explore`, `nia_research`, `nia_package_search_hybrid`, `context`, `tracer`, `auto_subscribe_dependencies`, `nia_write`, `nia_mkdir`, `nia_mv`, `nia_rm`, `nia_advisor` [V — live tool list this session] | runtime ToolSearch |
| PR-relevant tools | `nia_grep` / `search` (ground claims against indexed repo), `tracer` (live repo search without indexing), `nia_research` (discovery mode — NOT for code generation per Leo's T14 rule), `nia_package_search_hybrid` (verify third-party API shapes), `context` (persist findings for next session) [V] | same |

### 1.3 Cloud PR tooling

**Nia does not post PR comments, does not have a GitHub App, does not auto-review PRs.** [V — confirmed via docs.trynia.ai/api-guide and docs.trynia.ai/llms.txt]. It exposes a `POST /github/tracer` "live GitHub code search agent" endpoint but no webhook or review surface. Nia is an *input* to a PR-review flow, not an actor on the PR.

### 1.4 Integration hooks

- Direct REST API (OpenAPI spec at `https://docs.trynia.ai/openapi-docs.yaml` [V])
- MCP HTTP endpoint `https://apigcp.trynia.ai/mcp` [V]
- Python + TypeScript SDKs [V — docs.trynia.ai/sdk/quickstart.md]
- No GitHub App. No webhooks documented.

### 1.5 Automation fit

**Role:** Grounding layer for the codex automation itself AND for Greptile (see §5.1). Before a codex cron job pushes a branch, it can:
1. `nia_grep` to verify the function it just edited still has no duplicate definitions elsewhere in the repo
2. `nia search query` to pull cross-file context into the commit message
3. `tracer` to spot-check a third-party SDK shape without indexing

**Minimum instrumentation:** set `NIA_API_KEY` env var, ensure the `nia` MCP is configured in `~/.claude.json` (already done — Leo has access today), add one `context` call at task end to persist findings.

### 1.6 Gotchas

- `nia_research(mode='deep')` hallucinates schemas (Leo's T14 incident). Use `quick` mode for URL discovery only; never paste its code into production. [V — Leo memory + skill file]
- Rate limits enforced via `X-RateLimit-*` + `X-Monthly-Limit` response headers; 429 on exceed. [V — docs.trynia.ai/api-guide]
- Actual pricing tiers: `[UNVERIFIED]` — docs page references pricing but the tiers page was not fetched; check app.trynia.ai.

### 1.7 Authoritative docs

- https://docs.trynia.ai/integrations/installation/cli.md
- https://docs.trynia.ai/integrations/installation/mcp.md
- https://docs.trynia.ai/api-guide
- https://docs.trynia.ai/llms.txt (doc index)
- https://docs.trynia.ai/openapi-docs.yaml

---

## 2. Greptile (`greptile.com`)

**One-line role:** Cloud PR review bot. Owns the comment-on-draft-PR lane.

### 2.1 CLI surface

Greptile does **not ship a standalone CLI**. [V — docs.greptile.com/llms.txt lists no CLI page]. The "CLI surface" is effectively the MCP server consumed from Claude Code / Cursor / Codex CLI.

### 2.2 MCP server

| Item | Value | Source |
|---|---|---|
| Install (Claude Code) | `claude mcp add --transport http greptile https://api.greptile.com/mcp --header "Authorization: Bearer $GREPTILE_API_KEY"` [V] | greptile.com/docs/mcp-v2/setup.md |
| Transport | HTTP (not stdio) [V] | same |
| API key source | `app.greptile.com/settings/organization/api` [V] | same |
| Env var | `GREPTILE_API_KEY` [V] | same |

**MCP tools exposed** (PR-relevant subset) [V — greptile.com/docs/mcp-v2/tools.md]:

| Tool | Purpose |
|---|---|
| `list_pull_requests` / `list_merge_requests` | Filter PRs by branch/author/state |
| `get_merge_request` | Fetch PR details + review analysis |
| `list_merge_request_comments` | Fetch Greptile-generated comments, filter by `addressed: bool` |
| `search_greptile_comments` | Search across all historical Greptile comments |
| `list_code_reviews` / `get_code_review` | Query reviews by PR + status |
| `trigger_code_review` | **Programmatically fire a review on a PR** (requires repo + defaultBranch) |
| `list_custom_context` / `get_custom_context` / `search_custom_context` / `create_custom_context` | Manage team coding standards (org memory) |

### 2.3 Cloud PR tooling (what it actually does)

- GitHub App auto-reviews PRs matching configured triggers (labels, authors, branches, keywords) within ~3 min [V — greptile.com/docs/quickstart]
- Posts inline review comments with severity levels (`strictness 1-3`) [V — greptile.json reference]
- Renders a "Fix in X" button per comment, opening Claude Code / Cursor / Devin with the fix context preloaded [V — docs.greptile.com intro]
- Default behavior: **`triggerOnDrafts: false`** — drafts are skipped unless explicitly opted in [V — greptile-json-reference]
- Manual trigger: tag `@greptileai` in a PR comment [V — quickstart]
- Skip config: `skipReview: "AUTOMATIC"` to disable auto but keep manual [V — greptile-json-reference]

### 2.4 Integration hooks

- **GitHub App** — install via Greptile dashboard → Settings → Connect [V]
- **`greptile.json`** at repo root OR `.greptile/` folder with cascading per-dir rules [V — greptile-config docs]
- **Jira integration** for ticket-aware reviews [V — llms.txt]
- **MCP `trigger_code_review` tool** is the programmatic-fire hook [V]
- Webhook/REST API shape beyond MCP: `[UNVERIFIED]` — not surfaced on the MCP v2 docs index.

### 2.5 Automation fit

**Role:** Post-push PR reviewer. Order:
1. Codex automation pushes branch
2. `gh pr create --draft ...`
3. Vidux automation flips `triggerOnDrafts: true` **OR** explicitly calls `trigger_code_review` via MCP
4. Wait ~3 min (Greptile indexing latency)
5. Codex automation reads `list_merge_request_comments(addressed: false)` and either auto-addresses simple ones (auto-fix workflow) or tags them as follow-ups in the next PLAN

**Minimum instrumentation:**
- Install GitHub App once per repo (Resplit, StrongYes, Vidux)
- Add `greptile.json` to each repo with the review profile Leo wants (likely `strictness: 2`, `triggerOnDrafts: true` for the codex lane)
- Add `GREPTILE_API_KEY` to the automation env
- Index latency: first-time repo indexing is **1–2 hours** [V — quickstart]

### 2.6 Gotchas

- Auto-fix workflow docs say "requires an IDE" — meaning the human-in-loop flow is IDE-coupled. For **headless** codex-cron auto-fix, you can still call the MCP tools directly and apply diffs programmatically; Greptile automatically marks comments `addressed` when the files change [V — auto-fix.md]. The "IDE required" wording is UX not protocol.
- 1-2h first-index blocks the first review. Don't bake that into timing budgets.
- Pricing: **$30/seat/month, 50 reviews included, $1/additional review** [V — greptile.com/pricing]. Cost scales with automation volume — a cron that opens 10 PRs/day on one seat burns through the 50 cap in 5 days. Leo needs to monitor this.
- Genius API: $0.45/request [V]. `[UNVERIFIED]` whether MCP `trigger_code_review` calls count against the 50-review allowance or against Genius API.

### 2.7 Authoritative docs

- https://www.greptile.com/docs/llms.txt (index)
- https://www.greptile.com/docs/mcp-v2/setup.md
- https://www.greptile.com/docs/mcp-v2/tools.md
- https://www.greptile.com/docs/mcp-v2/auto-fix.md
- https://www.greptile.com/docs/code-review/greptile-json-reference.md
- https://www.greptile.com/docs/quickstart.md
- https://www.greptile.com/pricing

---

## 3. Sentry (`sentry.io`) — core platform

**One-line role:** Error monitoring + release/commit attribution. The "PR-adjacent" piece: it comments on PRs about suspect commits when an error appears in prod.

### 3.1 CLI surface (`sentry-cli`)

| Command | Purpose | Source |
|---|---|---|
| `sentry-cli releases new "$VERSION"` | Create release [V] | docs.sentry.io/cli/releases |
| `sentry-cli releases set-commits "$VERSION" --auto` | Associate commits with release (suspect commits) [V] | same |
| `sentry-cli releases set-commits "$VERSION" --commit "owner/repo@sha"` | Manual commit association [V] | same |
| `sentry-cli releases finalize "$VERSION"` | Finalize release [V] | same |
| `sentry-cli deploys new --release "$VERSION" -e <env>` | Mark deploy (prod/preview/etc) [V] | same |
| `sentry-cli sourcemaps upload` | Upload source maps [V] | same |
| `sentry-cli repos list` | List configured repos [V] | same |

Auth: `SENTRY_AUTH_TOKEN` env var [V — docs.sentry.io/cli].

### 3.2 MCP server

| Item | Value | Source |
|---|---|---|
| Install (Claude Code, cloud OAuth) | `claude mcp add --transport http sentry https://mcp.sentry.dev/mcp` [V] | docs.sentry.io/product/sentry-mcp |
| Install (plugin) | `claude plugin install sentry-mcp@sentry-mcp` [V] | github.com/getsentry/sentry-mcp |
| Local stdio | `npx @sentry/mcp-server` [V] | docs.sentry.io/product/sentry-mcp |
| Auth (cloud) | Device-code OAuth — browser opens on first run [V] | same |
| Auth (self-hosted stdio) | Manual user auth token with scopes `org:read`, `project:read`, `event:write`, `project:write` [V] | github.com/getsentry/sentry-mcp |
| Confirmed tool names | `search_events`, `search_issues` [V — both docs.sentry.io and GitHub README mention these by name] |
| Full tool inventory | `[UNVERIFIED]` — docs don't enumerate all tools; README notes broader "issues, errors, projects, Seer analysis" access |

### 3.3 Cloud PR tooling (GitHub integration, not Seer)

**Sentry GitHub integration (separate from Seer)** [V — docs.sentry.io/organization/integrations/source-code-mgmt/github]:

- **Suspect commits** → posts PR comments when a new error is traced back to a commit in that PR
- `fixes SENTRY-ABC-123` in commit message auto-links resolution
- Permissions needed: Issues, Contents, Pull Requests, Checks, Commit Statuses, Webhooks (Read & Write); Administration + Metadata (Read); org Members (Read)
- **Not required** for Seer/Code Review — those are separately enabled

### 3.4 Integration hooks

- GitHub App (Sentry GitHub integration)
- `sentry-cli` for release/commit wiring
- REST API
- MCP HTTP endpoint

### 3.5 Automation fit

**Role:** Post-merge feedback loop — tells the next vidux PLAN whether the last deploy broke anything. NOT a pre-merge PR gate.

**Minimum instrumentation in a codex cron:**
1. After merge, codex runs `sentry-cli releases new "$(git rev-parse HEAD)"`
2. `sentry-cli releases set-commits "$VERSION" --auto`
3. `sentry-cli releases finalize "$VERSION"`
4. (Optional) `sentry-cli deploys new ... -e production` after deploy
5. Next cron tick: Claude reads the Sentry MCP with `search_issues` scoped to `release:$VERSION` to detect regressions

### 3.6 Gotchas

- Requires `SENTRY_AUTH_TOKEN` in the automation env
- MCP server docs note: "production-ready, but MCP is still evolving. Expect rough edges." [V]
- Self-hosted Sentry requires token-based auth; cloud uses OAuth only
- The GitHub integration's PR-comment behavior is **post-deploy suspect-commit**, not pre-merge review. Don't confuse it with Seer Code Review.

### 3.7 Authoritative docs

- https://docs.sentry.io/cli/releases/
- https://docs.sentry.io/product/sentry-mcp/
- https://github.com/getsentry/sentry-mcp
- https://docs.sentry.io/organization/integrations/source-code-mgmt/github/

---

## 4. Seer (`docs.sentry.io/product/ai-in-sentry/seer`)

**One-line role:** Sentry's AI debugging agent. Two distinct PR-facing features: **Autofix** (post-error, opens new PRs) + **AI Code Review** (pre-merge, comments on existing PRs).

### 4.1 CLI surface

No dedicated Seer CLI. [V — only `sentry-cli` exists; Seer is managed via Sentry UI + GitHub integration]. Trigger surface for Seer is `@sentry review` in a PR comment, or `@sentry` in Slack, or UI-driven from issue details.

### 4.2 MCP server

Seer does not ship a separate MCP. It's accessed through the Sentry MCP (see §3.2) — specifically the "Seer analysis access" mentioned in the docs. [V]. Specific Seer tool names in the MCP: `[UNVERIFIED]`.

### 4.3 Cloud PR tooling

**4.3.a — Autofix** [V — docs.sentry.io/product/ai-in-sentry/seer/autofix]:
- Triggered automatically when an issue has 10+ events + high fixability score AND an agent is configured for background handoff
- OR manually from issue-details page OR from Slack
- Outputs: root-cause analysis, remediation recommendation
- Can **create new PRs** (new branch, code diff, possibly across multiple repos) OR checkout changes locally
- PR creation can be **disabled org-wide** via advanced settings

**4.3.b — AI Code Review / Error Prediction** [V — docs.sentry.io/product/ai-in-sentry/ai-code-review]:
- Triggered automatically when: PR is opened (non-draft), draft→ready transition, or new commits to ready PR
- **Skips drafts entirely** — if PR is draft at any time, review is skipped [V]
- Manual trigger: `@sentry review` comment on PR
- Outputs: inline review comments + GitHub status check (success / neutral / error / cancelled) + celebratory emoji on PR description
- Permissions: Pull Requests (R/W), Checks (R/W)
- **Enabling Code Review on a repo starts "active contributor pricing"** [V]

### 4.4 Integration hooks

- Sentry GitHub integration (reused)
- UI toggle in Seer SCM Settings per repo
- PR comment trigger `@sentry review`
- Slack integration for manual Autofix trigger

### 4.5 Automation fit

**Critical conflict with vidux draft-PR flow:** Seer Code Review **will not run on drafts**. If vidux automation opens drafts exclusively, Seer Code Review is silent until the PR flips to "Ready for review". This is the opposite of Greptile's configurable `triggerOnDrafts`.

**Options:**
1. Have the codex cron open a real (non-draft) PR instead of draft — lets Seer auto-review, loses the "draft = AI work in progress" semantic
2. Keep drafts; codex cron explicitly posts `@sentry review` on the PR to force a one-shot review
3. Skip Seer Code Review entirely for automation lanes; use it only for human-authored PRs

**Autofix is orthogonal** — it creates PRs in response to production errors, not in response to vidux plans. Best treated as a separate incoming lane the vidux PLAN must absorb.

### 4.6 Gotchas

- **Drafts are a hard skip** for Code Review — biggest mismatch with vidux's draft-first workflow
- Seer is a paid add-on on top of Sentry; "active contributor pricing" is billed per repo with Code Review enabled [V]
- GitHub-cloud only; GitHub Enterprise self-hosted not supported [V]
- Autofix PRs may span multiple repos — need to handle cross-repo context in vidux PLAN updates
- Seer subscription is distinct from base Sentry subscription; verify Leo has it active before assuming it works

### 4.7 Authoritative docs

- https://docs.sentry.io/product/ai-in-sentry/
- https://docs.sentry.io/product/ai-in-sentry/seer/
- https://docs.sentry.io/product/ai-in-sentry/seer/autofix/
- https://docs.sentry.io/product/ai-in-sentry/ai-code-review/

---

## 5. SYNTHESIS

### 5.1 Recommended stack composition — who owns what

| Lane | Service | Why |
|---|---|---|
| Pre-push grounding (codex reads repo before writing) | **Nia** | Already wired as MCP; `nia_grep`/`search`/`tracer` give grounded context without hallucination |
| Pre-merge draft-PR review | **Greptile** | Only service that supports drafts via `triggerOnDrafts` + programmatic `trigger_code_review` MCP tool |
| Pre-merge deep bug prediction (human PRs only) | **Seer Code Review** | Good for Leo's manual work; skips automation drafts anyway |
| Post-merge error feedback → next PLAN | **Sentry + `sentry-cli` release hooks** | Standard release-tracking loop; feeds suspect-commit comments back to vidux |
| Post-error autonomous fix (triage lane) | **Seer Autofix** | Treat its generated PRs as an *inbound* lane on vidux PLAN |

### 5.2 Order of operations (codex cron draft-PR flow)

```
codex cron tick starts
  ↓
read PLAN.md, pick next task
  ↓
(pre-flight) nia_grep / nia search  — verify no duplicate defs, gather context
  ↓
edit code
  ↓
git commit, git push origin <lane-branch>
  ↓
gh pr create --draft --title "..." --body "..."
  ↓
(optional) flip greptile.json triggerOnDrafts=true  OR  call Greptile MCP trigger_code_review
  ↓
wait ~3 min (Greptile review latency)
  ↓
Greptile MCP list_merge_request_comments(addressed=false)
  ↓
IF trivial comments: auto-fix, commit, push, mark addressed
  ↓
IF non-trivial: log into PLAN as follow-up task, leave PR draft
  ↓
(post-merge, separate cron) sentry-cli releases new/set-commits/finalize
  ↓
(next tick) Sentry MCP search_issues release:$VERSION → regression check
```

### 5.3 Dependency graph

```
Nia MCP (already live)
  └── used by both Claude and Greptile auto-fix loop

Greptile GitHub App
  ├── requires: repo pushed once, GitHub App installed, greptile.json committed
  ├── blocks on: 1-2h first-time indexing per repo
  └── used by: codex cron post-push

Sentry GitHub integration
  ├── requires: integration installed, repos linked, SENTRY_AUTH_TOKEN in env
  └── used by: sentry-cli release calls + Seer

Seer (Code Review + Autofix)
  ├── requires: Sentry subscription + Seer add-on active + GitHub integration
  ├── requires: Code Review toggled per repo (triggers "active contributor pricing")
  └── used by: human PRs (Code Review), production-error response (Autofix)
```

**Setup order:** Nia (done) → Sentry GitHub integration → `sentry-cli` in env → Greptile GitHub App + first-index wait → Seer toggle (last — cost implication).

### 5.4 Setup effort per service

| Service | Effort | Reasoning |
|---|---|---|
| Nia | **S** | Already installed; just formalize usage pattern in codex prompts |
| Greptile | **M** | GitHub App install + `greptile.json` per repo + first-index wait + MCP wiring + monitoring the 50-review/seat cap |
| Sentry (base + CLI) | **S-M** | `sentry-cli` in CI/cron env + release hooks in post-merge script + GitHub integration install (one-time) |
| Seer | **S** | UI toggle per repo; no code — BUT Leo must decide per-repo whether the "active contributor pricing" is worth it |
| Custom `/sentry` skill | **M** | Wrap `sentry-cli releases new/set-commits/finalize/deploys new` + Sentry MCP `search_issues` + Seer `@sentry review` trigger into one cohesive surface, replacing plugin-provided `sentry-*` skills |

### 5.5 Unknowns to resolve before Phase 5.3 design

1. **Greptile billing model under automation pressure** — do MCP-triggered reviews (`trigger_code_review`) count against the 50/seat allowance, or against the $0.45 Genius API? At 10 codex PRs/day this matters. Need to email Greptile sales OR test empirically on one repo and watch `nia usage`-equivalent.
2. **Sentry MCP full tool list** — docs don't enumerate all tools. Need to connect via `claude mcp add` and run `/mcp` to dump the actual tool inventory before the `/sentry` skill can wrap them.
3. **Draft-PR policy decision** — Greptile supports drafts, Seer Code Review does not. Does vidux open drafts (codex lane) or real PRs (auto-ready lane)? This is a doctrine call, not a tooling call. Recommendation: drafts for codex, real PRs for human-reviewed merges.
4. **Seer Autofix inbound lane** — if Autofix opens PRs into a repo, how does vidux's PLAN authority absorb them? Does the cron detect `seer/autofix-*` branches and promote them into PLAN.md tasks? Or are Autofix PRs out-of-band?
5. **Repo indexing cost on Greptile** — Resplit is large. First-index = 1-2h. If Leo wants to enable Greptile on Resplit, Vidux, and StrongYes, that's up to 6h of blocking before first review lands. Schedule this overnight, not during an active cron window.

### 5.6 Minimum viable wiring (if Leo wants to ship TODAY)

1. Install Greptile GitHub App on `vidux` repo only (smallest first-index cost)
2. Add `greptile.json` with `triggerOnDrafts: true, strictness: 2`
3. Set `GREPTILE_API_KEY` in `~/.zshrc`
4. Add Greptile MCP to `~/.claude.json`
5. Wait 1-2h for first index
6. Test: manually open a draft PR on vidux, confirm comments appear within 5 min
7. **Only then** extend to Resplit + StrongYes + wire into codex cron prompts

Everything else (Seer toggle, Sentry release hooks, custom `/sentry` skill) is Phase 5.3.2+.

---

## Appendix A — Claims marked `[UNVERIFIED]`

1. Nia pricing tier breakdown (need to fetch app.trynia.ai)
2. Whether Greptile MCP `trigger_code_review` counts against 50-review/seat cap or Genius API $0.45/request
3. Greptile webhook/REST API shape outside MCP
4. Full Sentry MCP tool inventory (only `search_events`, `search_issues` named in docs)
5. Seer-specific tool names within Sentry MCP
