# Private ChatGPT Shadow app

This is the reviewed remote coaching bridge for Leo's private ChatGPT account.
It exposes two static, read-only MCP tools: one describes how to write a
chief-of-staff brief and one describes how to shape a compact Shadow goal.

The Worker has no storage, secrets, private data sources, mutation tools, or
local network access. The endpoint can therefore be reached without a login,
but the ChatGPT app that presents it remains private to Leo's account. Knowing
the endpoint reveals only the same public writing contracts in this repository.

This is not a second Shadow. It cannot see the computer board or a repository
plan, and it cannot claim, complete, verify, send, deploy, or publish work.
ChatGPT's connected data apps provide cloud facts; local Shadow remains the
authority for local work and proof.

## Verify and deploy

From this directory:

```bash
pnpm install --frozen-lockfile
pnpm run types
pnpm run check
pnpm run deploy
```

After deployment, a real MCP client must read back `tools/list` at `/mcp` and
confirm that only the two reviewed coaching tools appear. The private ChatGPT
app must then show the same two tools. Opening `/mcp` in a browser is not a
protocol test.
