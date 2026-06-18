# Figma — Net New Project Runbook

> **Captured 2026-05-25 from Leo's runbook paste.** Authoritative step-by-step for kicking off Figma work on any new vidux project. Pair with `your Figma skill runbook` (the single Figma entry point) for the full skill router.

---

## 1. One-time machine setup (skip if already done)

```bash
# Claude Code
claude mcp add figma --transport sse --url https://mcp.figma.com/sse

# Codex (if you also use it)
codex mcp add figma --url https://mcp.figma.com/mcp
codex --enable rmcp_client
codex mcp login figma
```

Then quit + reopen the client (Cmd+Q). **MCP servers only load at startup.**

---

## 2. Authenticate (first session only)

In Claude Code, on first Figma tool call:

1. Call `mcp__figma__authenticate` → returns an auth URL.
2. Open the URL → approve in browser.
3. Copy the full localhost callback URL it redirects to.
4. Paste it back: `mcp__figma__complete_authentication({ callback_url })`.

OAuth token persists across sessions. One-time per machine.

---

## 3. Verify

```bash
/mcp                          # figma should show "connected"
```

Then in-tool:

```
ToolSearch({query: "figma", max_results: 20})
```

You should see: `use_figma`, `get_design_context`, `get_screenshot`, `get_metadata`, `create_new_file`, `generate_diagram`, `get_code_connect_suggestions`, `get_context_for_code_connect`, `search_design_system`, `whoami`.

---

## 4. Net-new project kickoff

For a brand new project, do this once:

1. **Decide direction:** code → Figma, or Figma → code?
2. **If creating a Figma file from scratch:** invoke `/figma:figma-create-new-file design "<ProjectName>"` — it handles whoami + planKey and returns a `file_key` + `file_url`.
3. **If working from an existing Figma file:** grab the frame URL. Convert node-id from `X-Y` (URL) to `X:Y` (API).
4. **Pin the brand skill if one exists** — `/brand-strongyes`, `/brand-leojkwan`, `/brand-snowcubes`, etc. Project tokens override raw Figma values.

---

## 5. First implementation call (Figma → code)

Paste your Figma URL → Claude. Say:

> "Implement this. Use `<project brand skill>` tokens."

Claude (with `/figma` loaded) will:

1. Parse `fileKey` + `nodeId`.
2. `get_design_context` → structured data.
3. `get_screenshot` → visual reference.
4. `get_variable_defs` → tokens.
5. `get_code_connect_map` → check for existing component mappings.
6. Translate to project conventions.
7. Validate 1:1 against the screenshot.

---

## 6. First implementation call (code → Figma)

Say:

> "Build this page in Figma from `<file path>`."

Claude will load `/figma:figma-generate-design` + `/figma:figma-use`, discover design system components, and assemble incrementally.

---

## 7. Pick your lane after that

| Doing | Load |
|---|---|
| Pull design context → write code | `/figma` only (Design → Code workflow) |
| Write/edit Figma nodes via Plugin API | `/figma:figma-use` (mandatory) |
| Build a screen/modal/page from code | `/figma:figma-generate-design` + `/figma:figma-use` |
| Build a design system | `/figma:figma-generate-library` + `/figma:figma-use` |
| Code Connect mapping (`.figma.ts`) | `/figma:figma-code-connect` |
| New blank Figma file | `/figma:figma-create-new-file` |
| Mermaid → FigJam diagram | `/figma:figma-generate-diagram` |

---

## 8. Common first-day gotchas

- **Node ID format** — URL uses `X-Y`, API wants `X:Y`. Always convert.
- **Restart after `mcp add`** — Cmd+Q + reopen, or tools won't appear.
- **Truncated `get_design_context`** — fall back to `get_metadata` → fetch children individually.
- **Asset URLs** — MCP serves localhost URLs. Pass them through. Do NOT install new icon packages.
- **Figma Make files** — `get_screenshot` and `get_metadata` are unsupported. Use live preview for visual reference. (Make MCP support hasn't shipped yet.) See also: memory `reference_figma_make_mcp_state.md`.
- **Org-locked files** — personal OAuth can't see them. File must be readable by your account.

---

## When to invoke this from inside a vidux project

Any new vidux project that will have a visual surface (Mac UI, iOS UI, web, marketing site) should:

1. Run Step 1 (machine setup) — should already be done on Leo's primary Macs.
2. Run Step 4 (kickoff) — creates the canonical Figma file for the project.
3. Add the resulting `file_url` to the project's `PLAN.md` under a `## Design surface` section so any future agent (Claude or Codex) can pick it up.

For projects that are infra-only (servers, CLIs, MCPs) — skip Figma entirely. Don't generate a file for the sake of having one.
