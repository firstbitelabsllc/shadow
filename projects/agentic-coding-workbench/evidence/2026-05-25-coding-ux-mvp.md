# /coding UX MVP Finish Line

## What the user should understand in the first 10 seconds

- This is the local coding command center for Leo's Mac, not a generic dashboard.
- The main job is to prove and debug code work locally before trusting cloud CI, remote agents, or primary-checkout edits.
- The current MVP path is: pick a repo/lane, run a bounded local proof, inspect the result, then hand a failing result to a verifier/editor agent with evidence attached.
- The page is allowed to run only named, bounded actions. It is not an arbitrary shell.
- Fresh-main proof, local-branch proof, peer/M4 proof, and handoff-only packets are different states and must stay visibly different.
- A green page should mean "the latest local proof artifacts are green," not merely "the app loaded."

## What is currently confusing or too dense

- The first viewport has a good title and four action buttons, but it immediately expands into many proof surfaces. The operator has to infer which pane is the next action versus which pane is historical/debug context.
- "All 12 local lanes are green" reads too final when the screenshot also shows warning packets, handoff-only M4 packets, review scout transport caveats, source-state caveats, and advanced substrate below. MVP copy should name the exact proof scope.
- The page mixes product-level actions with implementation substrate: FirstBite lanes, peer proof, M4 packets, review scout packets, active work, repo launchers, run history, routing map, model routes, raw capability catalog, workers, recent runs, terminal, and isolated agent lanes all appear as peers.
- The action vocabulary is inconsistent. The same page says Prove Local CI, Dry Critical, Run Critical, Run Now, Status, Public Matrix, Preflight Lane, Run Action, Detached, Handoff, and Codex Editor. A human operator needs fewer top-level verbs.
- Proof artifacts are visible, which is good, but their hierarchy is unclear. Report/log/packet/link/status URL/final message/patch should roll up into one "Evidence" language.
- The terminal is useful but appears late and reads like the real center of gravity. For MVP, the visible debugger should summarize state first and let raw logs expand from there.
- Advanced routing/model/source/MCP details are valuable for agents and power users, but they compete with the primary "what do I run next?" decision.
- There is not enough source-state framing near the action buttons. The operator should see fresh main vs dirty local branch vs peer packet before trusting a lane result.

## MVP UI structure: panes, labels, buttons, status/debugger, local usage, proof artifacts

### 1. Top command bar

Purpose: orient the operator and expose only the safest next actions.

Labels:
- Title: "Local Coding Command Center"
- Status line: "This Mac: [host] · Source: [fresh main/local branch/dirty/unknown] · Local CI: [green/red/stale] · Workers: [n running]"
- Primary buttons:
  - "Prove Local CI"
  - "Run Resplit Autobot"
  - "Inspect Latest Failure"
  - "Delegate Verifier"
- Secondary buttons:
  - "Refresh Proof"
  - "Open Evidence"
  - "Advanced"

MVP rule: top buttons should launch or inspect a known workflow. They should not expose every tool action.

### 2. Current proof pane

Purpose: answer "can I trust this machine's local proof right now?"

Show:
- Repo/lane summary grouped by repo: Resplit Web, Resplit iOS, StrongYes Web, Moussey.
- Per repo: pass/red/stale counts, source head, remote main head, dirty/local branch state, latest report path.
- One clear callout when proof is handoff-only or peer-only.

Buttons:
- "Dry Run"
- "Run"
- "Report"
- "Log" only when a lane is red or selected.
- "Create Handoff" only for red/stale lanes.

MVP copy standard:
- "Fresh main green"
- "Local branch green"
- "Dirty checkout proof"
- "Peer packet only"
- "Stale or missing proof"

### 3. Failure/debugger pane

Purpose: make the next repair step obvious.

Show:
- Latest selected failure or latest run.
- Exit code, failing lane, cwd, command, source state, elapsed time.
- Human summary first, raw tail second.
- Evidence links: report, log, patch, worker status, final message.
- Teardown state when worktrees/ports are involved.

Buttons:
- "View Report"
- "View Log"
- "Stage Verifier"
- "Preview Patch" when a patch exists.

Raw logs should be collapsed by default after a short summary.

### 4. Agent worker pane

Purpose: show whether background agents are doing useful bounded work.

Show:
- Running, completed, failed/stale counts.
- Worker cards with: action label, repo/lane, status, updated time, final answer availability, log size, Codex route hint.
- Final message first; log tail collapsed.

Buttons:
- "Open Final"
- "Open Log"
- "Rerun Probe" for read-only probes only.

MVP boundary: no arbitrary prompt box yet. Workers are launched from named actions or handoffs.

### 5. Evidence/history pane

Purpose: make local usage and proof artifacts auditable without reading JSONL.

Show:
- Recent runs grouped by today/previous.
- Counts: completed, failed, running, local minutes.
- Artifact chips: report, log, patch, packet, link.
- Clear ownership: Mac Studio, M4, or handoff-only.

Buttons:
- "Replay Summary"
- "Open Evidence"
- "Create Handoff" for failed runs.

### 6. Advanced substrate drawer

Purpose: preserve deep capability visibility without making it the landing experience.

Keep behind Advanced:
- Routing map.
- Model routes.
- Capability catalog.
- MCP server names/env-key names.
- Skill symlink/source inventory.
- Source registry.
- Codex settings and provider routing details.
- Full local-CI lane manifest grid when the current proof pane already summarizes it.

Advanced should be collapsed by default and visually separated from MVP operator controls.

## What can stay advanced/collapsed

- Full skill inventory and symlink/source paths.
- Full MCP server list and env-key names.
- Provider/base URL/model route matrices.
- Nia source ids, duplicate source ids, and route-hardening details.
- Peer proof packet internals unless a peer is selected.
- M4 fresh-clone packet commands unless the user opens the packet.
- Review scout packet internals unless the user opens the packet.
- Full repo-declared lane launcher grid when all the operator needs is repo-level health plus selected lane details.
- Raw terminal tail after a concise debugger summary.
- Old run history beyond the latest 5-10 items.
- Detached worker log tails until a worker is selected.
- Codex Editor and other edit-capable lanes unless entered through a failed-run handoff with evidence attached.

## Suggested exact copy for the top of /coding

Title:

> Local Coding Command Center

Subtitle:

> Prove code work on this Mac before trusting CI, remote agents, or primary-checkout edits. Start with local CI and Resplit Autobot, inspect the evidence, then delegate only bounded verifier/editor agents from a failing proof.

Current mission card:

> Make this Mac the base station for local coding agents.
>
> Run repo-declared lanes, keep source state visible, and turn failures into evidence-backed handoffs. Green means the latest proof artifact is green for the named source, not that every launch gate is done.

Status strip labels:

- `Host`
- `Source state`
- `Local CI`
- `Workers`
- `Usage`
- `Latest proof`

Primary action labels:

- `Prove Local CI`
- `Run Resplit Autobot`
- `Inspect Latest Failure`
- `Delegate Verifier`

Button helper copy:

- Prove Local CI: `Dry-run or execute the repo-declared FirstBite lanes.`
- Run Resplit Autobot: `Run the bounded public matrix from the local command.`
- Inspect Latest Failure: `Open the newest red lane with report, log, command, and source state.`
- Delegate Verifier: `Start a bounded agent only from selected evidence.`

Warning copy:

> This proof is from a local branch or dirty checkout. Do not report it as fresh-main proof.

> This packet was prepared for another Mac. It is not remote execution proof until that Mac records a completed run.

> This action can inspect and write evidence. It must not edit the primary checkout.

Empty state copy:

> No local proof is loaded yet. Refresh proof or dry-run the critical lanes.

MVP finish-line test:

> A human should be able to open `/coding`, know which proof is current, see whether it came from fresh main or local state, run one safe next action, and open the evidence for any red result without reading raw JSON or understanding the underlying MCP/tool substrate.
