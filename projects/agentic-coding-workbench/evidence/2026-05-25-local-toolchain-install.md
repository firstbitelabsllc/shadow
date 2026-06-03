# Local coding toolchain install proof - 2026-05-25

## Result

The six-specialist research split is now integrated into the local Moussey coding cockpit as a visible, bounded toolchain inventory. `/coding` reports which local coding-agent tools are installed, which ones still need provider configuration, and which heavier surfaces remain deferred instead of pretending the browser can already run arbitrary agent edits.

Live URL:

```text
http://127.0.0.1:4321/coding?fresh=c51-agent-toolchain
```

Browser proof:

```text
/tmp/moussey-c51-agent-toolchain-verified.png
```

## Installed local coding tools

- `aider` installed at `/Users/leokwan/.local/bin/aider`; version `aider 0.86.2`. Status in `/coding`: `installed`. MVP use: disposable-worktree patch worker after a wrapper exists.
- `opencode` installed at `/opt/homebrew/bin/opencode`; version `1.15.10`. Status in `/coding`: `needs-config`. MVP use: detached local-agent worker after provider/model config is proven without exposing secrets.
- `goose` installed at `/opt/homebrew/bin/goose`; version `1.35.0`. Status in `/coding`: `needs-config`. MVP use: MCP/provider-oriented local agent probe after config proof.
- `Continue` installed in VS Code and Cursor; version `1.2.22` in both. Status in `/coding`: `installed`. MVP use: external IDE handoff, not direct web-app control.
- `Cline` installed in VS Code and Cursor; version `3.84.0` in both. Status in `/coding`: `installed`. MVP use: human-supervised IDE agent path, not primary autonomous worker yet.
- `OpenHands` remains `deferred`. Reason: heavier sandbox/server surface than the current Moussey MVP needs.

## Installed local models

- `qwen3:8b`, 5.2 GB, Q4_K_M, thinking-capable in Moussey.
- `deepseek-r1:8b`, 5.2 GB, Q4_K_M, thinking-capable in Moussey.
- `gemma3:12b`, 8.1 GB, Q4_K_M, generalist route; not advertised as explicit Ollama thinking in Moussey.
- `qwen2.5:0.5b`, 397 MB, Q4_K_M, fast fallback/proof model; not a serious coding-agent brain.

Qwen3 API smoke:

```text
curl http://127.0.0.1:11434/api/generate ... {"model":"qwen3:8b","think":true,"stream":false}
response: api-thinking-ok
thinking: present
```

## Moussey implementation

- `lib/capability-catalog.ts` now inventories installed agent tools and adds a `Local Agent Tools` routing-readiness item.
- `lib/capability-catalog.test.ts` now covers fake CLI/editor probes so the inventory stays deterministic in tests.
- `app/coding/page.tsx` now renders a `Local Agent Toolchain` panel below model routes with one card per tool and explicit config/next-action text.

This is inventory and routing truth only. It does not grant arbitrary shell or edit authority from the browser. The next product slice is an allowlisted detached-worker wrapper that can run one selected tool in a disposable worktree and return a patch artifact for review.

## Verification

- `node --test --import tsx lib/capability-catalog.test.ts app/api/coding/capabilities/route.test.ts` passed `7/7`.
- `npm run test:brain-dispatcher` passed `161/161`.
- `npx tsc --noEmit --pretty false` passed.
- `./scripts/moussey-server.sh --build` passed with the known local-CI artifact-route Turbopack NFT warning.
- `./scripts/moussey-server.sh --restart` restored live app on `http://127.0.0.1:4321`.
- `GET http://127.0.0.1:4321/api/health` returned `ok:true`.
- `GET http://127.0.0.1:4321/api/coding/capabilities` reported `agent-tools` readiness `ready`, with `3` installed tools and `2` config-gated installed CLIs.
- Playwright loaded `http://127.0.0.1:4321/coding?fresh=c51-agent-toolchain`, found `Local Agent Toolchain`, `aider`, `opencode`, `Goose`, `Continue`, `Cline`, `OpenHands`, and `Model Routes`, captured `/tmp/moussey-c51-agent-toolchain-verified.png`, and reported zero console/page errors.
