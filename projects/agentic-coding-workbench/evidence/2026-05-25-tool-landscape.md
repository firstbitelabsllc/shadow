# Local coding-agent tool landscape

Date: 2026-05-25

Scope: practical local/open coding-agent IDE and CLI tools for the Moussey/Vidux command-center MVP. Selection lens is what can become a reliable `/coding` action, detached worker, external IDE handoff, or local-model route without weakening the existing disposable-worktree and proof-first cockpit.

## Top 3 recommended tools for this MVP

### 1. aider

Why it belongs first:

- Best fit for a bounded Moussey worker that produces inspectable patches in an isolated worktree.
- CLI-first, git-aware, easy to wrap as `POST /api/coding/workers` or a `/coding` action.
- Supports local Ollama models directly; official docs show `OLLAMA_API_BASE=http://127.0.0.1:11434` and `aider --model ollama_chat/<model>`.
- Small operational surface compared with a full IDE extension or browser app.
- Good complement to existing Codex lanes: use aider for small, concrete edits where the prompt can name files, tests, and expected patch shape.

Moussey integration:

- `/coding` action: `aider-verifier` or `aider-editor` on a disposable worktree, with explicit file allowlist and final `git diff --check`.
- Worker: detached background worker that writes stdout/stderr, final summary, and patch file to `~/.moussey/coding-workers` / `~/.moussey/coding-patches`.
- External IDE: optional terminal pane route; no need to embed an IDE to prove value.
- Local model route: Ollama via `ollama_chat/<model>` for low-risk documentation, targeted code edits, and local-only review; cloud model fallback for tricky refactors.

Low-risk normal macOS install command to record, not run:

```bash
brew install aider
```

Useful model commands to record only after Ollama/model choice is explicit:

```bash
export OLLAMA_API_BASE=http://127.0.0.1:11434
aider --model ollama_chat/<model>
```

Sources:

- https://aider.chat/docs/llms/ollama.html
- https://formulae.brew.sh/formula/aider

### 2. opencode

Why it belongs second:

- Terminal-native open-source coding agent, which matches Moussey's current worker/action architecture better than an IDE-only extension.
- Strong local-model story through Ollama; Ollama's official integration page says OpenCode is an open-source AI coding assistant that runs in the terminal and recommends a large context window.
- Good candidate for multi-agent experiments because each worker can run a separate opencode session against a separate worktree/port.
- More "agentic" than aider, so it is a better sandbox for delegated end-to-end attempts once the patch preview and worker monitor are boring.

Moussey integration:

- `/coding` action: `opencode-local-agent-probe`, first read-only, then edit-capable only inside disposable worktrees.
- Worker: one opencode session per lane; capture transcript/log/final message and convert diff to patch preview.
- External IDE: optional, but MVP should treat it as a terminal worker before adding editor coupling.
- Local model route: Ollama launched/configured opencode route; require explicit tool-calling/context checks before trusting local edit runs.

Low-risk normal macOS install command to record, not run:

```bash
brew install opencode
```

Useful local-model commands to record, not run:

```bash
ollama launch opencode --config
ollama launch opencode
```

Sources:

- https://docs.ollama.com/integrations/opencode
- https://formulae.brew.sh/formula/opencode
- https://opencode.ai/docs/

### 3. Goose

Why it belongs third:

- Open-source local AI agent from Block with CLI and Desktop surfaces.
- Strong MCP/extensions orientation, which maps well to Moussey's capability catalog and route matrix.
- Official docs explicitly support local LLMs through Ollama, LM Studio, Atomic Chat, Docker Model Runner, Ramalama, and related providers.
- Better than most IDE extensions for "command center" framing because it can act as a local agent surface and not only an editor sidebar.

Moussey integration:

- `/coding` action: `goose-capability-probe`, verifying provider config, MCP extension availability, and local tool-calling model behavior.
- Worker: useful for research/planning/diagnostic workers where MCP extension inventory matters as much as code editing.
- External IDE: Goose Desktop can be a sidecar, but Moussey should own status and proof rather than outsourcing the cockpit.
- Local model route: Ollama/local provider path, with a hard tool-calling requirement before enabling extensions.

Low-risk normal macOS install commands to record, not run:

```bash
brew install block-goose-cli
brew install --cask block-goose
```

Sources:

- https://goose-docs.ai/docs/getting-started/installation/
- https://goose-docs.ai/docs/getting-started/providers/

## Tools to skip or defer

### Continue

Defer, but keep in the ecosystem.

- It is excellent as an external IDE/autocomplete/chat surface and supports many providers including Ollama.
- It is less ideal as the first Moussey worker because its natural home is VS Code/JetBrains, not a detached `/coding` run with clean logs and patch artifacts.
- Use it as a "developer at the keyboard" integration later: open the handoff in Cursor/VS Code with Continue configured, while Moussey tracks the plan/run evidence.

Integration fit:

- External IDE handoff first.
- Local model route via Continue config/Ollama.
- Not a primary `/coding` worker until there is a stable CLI/headless contract worth wrapping.

Sources:

- https://docs.continue.dev/customize/models
- https://docs.continue.dev/guides/ollama-guide
- https://docs.continue.dev/guides/running-continue-without-internet

### Cline

Defer as a second-wave IDE/CLI route.

- Cline has the right primitives: VS Code extension, CLI, local models through Ollama/LM Studio, auto-approve controls, multi-root workspaces, and headless usage.
- It is still a bigger blast radius than aider/opencode for the current MVP because it wants editor integration, provider auth, and approval policy tuning before it feels calm.
- Good candidate after Moussey has a generic external-agent worker contract.

Integration fit:

- External IDE and CLI worker.
- `/coding` action for `cline-review` or `cline-docs-update` after a read-only probe.
- Local model route through Ollama/LM Studio, with compact prompt enabled for local inference.

Low-risk normal macOS install command to record, not run:

```bash
npm install -g cline
```

Sources:

- https://docs.cline.bot/running-models-locally/overview
- https://docs.cline.bot/cline-cli/overview
- https://docs.cline.bot/getting-started/installing-cline

### Kilo Code

Defer, but watch.

- Kilo is an open-source Cline/Roo-family VS Code agent and has candid local-model docs.
- Its own docs warn that local models are less impressive than cloud-hosted models and can loop, fail tool calls, or emit syntax errors.
- Useful if Leo wants a forkable VS Code extension path; less urgent than Cline because Cline is the more canonical migration target after Roo.

Integration fit:

- External IDE route.
- Local model route via Ollama; prefer `qwen3-coder:30b` or `devstral:24b` only as experiments, not trusted edit authority.

Sources:

- https://kilo.ai/docs/ai-providers/ollama
- https://kilo.ai/docs/getting-started

### Roo Code

Skip for new MVP work.

- Roo would have been relevant historically as a strong Cline-family VS Code agent.
- Current search/docs evidence says Roo Code products were shut down on May 15, 2026, and the official recommendation points users toward Cline or successors.
- Do not build a new Moussey integration against a sunset tool.

Sources:

- https://docs.roocode.com/
- https://www.bodegaone.ai/blog/roo-code-shutdown-alternatives

### OpenHands

Defer for heavier sandbox experiments.

- OpenHands is powerful and more "software-agent platform" than lightweight local worker.
- Its headless mode and JSONL output are attractive for automation, but headless always runs in always-approve mode according to docs, which is too much authority for the first Moussey MVP.
- Docker sandbox is the safer default; process sandbox has no isolation and can read/write/execute as the user account.
- Use later when Moussey wants a controlled "full agent lab" lane with Docker/devcontainer isolation and clear workspace volumes.

Integration fit:

- Worker only, not direct browser button at first.
- `/coding` action should start as a sandbox/config probe, not edit authority.
- Local model route possible through LM Studio/Ollama/SGLang/vLLM, but expect setup complexity.

Low-risk normal install command to record if `uv` is already installed, not run:

```bash
uv tool install openhands --python 3.12
```

Sources:

- https://docs.openhands.dev/openhands/usage/cli/installation
- https://docs.openhands.dev/openhands/usage/how-to/headless-mode
- https://docs.openhands.dev/openhands/usage/sandboxes/process
- https://docs.openhands.dev/modules/usage/llms/local-llms

## Reference baselines

### Codex

Use as the current proven baseline, not as the "new local/open" candidate.

- Already proven in Moussey: read-only probes, verifier/editor lanes, patch saving, worker final-message capture, MCP/OpenAI-docs/Nia routing attempts, and provider pinning.
- Official Codex config docs confirm user-level `~/.codex/config.toml`, `model_provider`, `oss_provider`, sandbox modes, MCP server config, and `features.multi_agent`.
- Keep Codex as the quality/safety baseline for what any new worker must match: isolated worktree, explicit provider, bounded output, final answer, diff stat, saved patch, teardown proof.

Integration fit:

- Existing `/coding` worker/action baseline.
- External IDE context via Codex IDE features if useful.
- Local model route through `--oss` / `oss_provider = "ollama" | "lmstudio"` only after separate quality proof.

Source:

- https://developers.openai.com/codex/config-reference

### Claude Code

Use as quality/reference baseline, not local/open primary.

- Strong practical coding baseline with terminal, IDE, MCP, skills, subagents, hooks, and broad workflow coverage.
- Auth and subscription state are real operational risks for this MVP; prior Moussey proof already saw Claude CLI auth failures on Studio.
- Good external-agent route when authenticated, especially for high-value complex tasks, but not the local/open default.

Integration fit:

- External CLI worker and IDE sidecar.
- Use only behind provider readiness checks and account/status visibility.

Sources:

- https://code.claude.com/docs/en/how-claude-code-works
- https://docs.anthropic.com/en/docs/claude-code/overview
- https://code.claude.com/docs/en/vs-code

### Cursor

Use as the human IDE baseline.

- Cursor CLI and Agent support MCP and non-interactive `--print`, and Cursor IDE remains useful for Leo-at-keyboard iteration.
- Not local/open, and local-model agent workflows are less clearly dependable than dedicated local-first tools.
- Best integration is a handoff button that opens the repo/task in Cursor with the right files and evidence, while Moussey remains the truth surface for local-CI and worker runs.

Integration fit:

- External IDE handoff.
- Possible CLI review/probe worker, but lower priority than existing Codex and new open/local CLIs.

Sources:

- https://cursor.com/cli/
- https://docs.cursor.com/en/cli/using
- https://docs.cursor.com/context/model-context-protocol

## Integration matrix

| Tool | Best Moussey surface | Worker fit | External IDE fit | Local model fit | MVP status |
| --- | --- | --- | --- | --- | --- |
| aider | `/coding` edit/verifier action | Excellent | Terminal sidecar | Good via Ollama | Recommend now |
| opencode | `/coding` agent worker | Excellent | Optional | Good via Ollama, needs tool/context proof | Recommend now |
| Goose | `/coding` capability/MCP worker | Good | Desktop sidecar | Good, tool-calling required | Recommend now |
| Continue | Handoff to VS Code/Cursor | Medium | Excellent | Good via Ollama/offline setup | Defer |
| Cline | Handoff plus later CLI worker | Good | Excellent | Good via Ollama/LM Studio, quality varies | Defer |
| Kilo Code | External IDE experiment | Medium | Good | Experimental, candid tool-call risks | Defer |
| Roo Code | None for new work | Poor now | Historical only | Historical only | Skip |
| OpenHands | Docker-sandbox lab worker | Good but heavy | Browser/UI sidecar | Possible but complex | Defer |
| Codex | Existing baseline | Excellent | Good | Possible via OSS provider | Keep baseline |
| Claude Code | Quality baseline | Excellent when auth works | Excellent | Not local/open default | Baseline only |
| Cursor | Human IDE baseline | Medium | Excellent | Not the strongest local route | Baseline only |

## Risks

### Auth

- Codex, Claude Code, Cursor, and many cloud-backed configs need local subscription/API auth; Moussey should expose provider readiness before launching.
- Cline and Goose can use local providers, but cloud provider auth still appears in normal setups.
- Continue external IDE setups may depend on Mission Control/user secrets if using cloud models.

### Token cost

- Roo/Cline-family tools can burn tokens quickly when auto-approve and large context are enabled.
- Codex/Claude/Cursor remain valuable baselines but need account and usage visibility in the cockpit.
- Aider is easier to constrain by file list and prompt shape; opencode and Goose need output caps and run budgets in Moussey.

### Local-model quality

- Local models are useful for narrow edits, docs, summarization, and first-pass reviews, but they are not yet drop-in replacements for frontier coding agents on ambiguous multi-file work.
- Tool-calling is the key gate. Goose docs warn models without tool calling fall back to chat-only behavior; Kilo docs warn local coding models can loop, fail tools, or produce syntax errors.
- Require per-tool "local model passed this exact probe" evidence before showing any local route as ready.

### Sandboxing

- Keep the existing Moussey pattern: disposable worktree, fixed cwd, env scrub, bounded stdout, patch preview, teardown proof.
- OpenHands process sandbox is specifically not isolated, so avoid it for browser-triggered actions.
- Headless OpenHands always-approve behavior is useful in CI-like lab lanes but too broad for a first MVP button.
- macOS browser automation may need wider permissions even inside disposable worktrees; keep this explicit like the current Codex verifier lane.

### Multi-agent support

- Codex has first-class multi-agent config and is already proven locally enough to be the baseline.
- Claude Code has subagents and strong ecosystem support but auth/subscription limits must be surfaced.
- opencode can be multi-agent by convention: one worker/session per worktree plus a Moussey coordinator.
- Goose extensions/MCP are promising for tool routing but should start as probes.
- IDE extensions are weaker as autonomous multi-agent infrastructure unless Moussey treats them as external handoff surfaces.

## Practical recommendation

Build the next Moussey/Vidux tool-landscape proof as three small workers, not one giant IDE bet:

1. `aider-local-patch-probe`: read task + file allowlist, make a tiny patch in a disposable worktree, save patch, run `git diff --check`.
2. `opencode-local-agent-probe`: read-only first, then patch-capable only after it proves command/file/tool behavior with the chosen model/provider.
3. `goose-mcp-local-probe`: inventory provider, extension/MCP readiness, and local tool-calling model behavior without editing source.

Keep Continue/Cline/Cursor as external IDE handoffs, and keep Codex as the reference implementation all new tools must measure against.
