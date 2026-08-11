# Leo private deployment receipt

Observed 2026-08-11 at 21:09 UTC:

- Cloudflare Worker version: `cfa77a27-6d1d-48a5-9dd7-b3332cc83c74`
- MCP endpoint: `https://shadow-private-coach.superfit.workers.dev/mcp`
- ChatGPT app: `asdk_app_6a7b8ee950848191b2c7850504d5c6e0`
- ChatGPT app version: `asdk_app_v_6a7b8ee950908191a4319113353d3a0f`
- Account state: connected, no authorization, development review status
- Discovered actions: `get_shadow_brief_contract` and
  `get_shadow_goal_contract`, both READ

The live protocol readback matched the checked-in tool list. The existing
08:00/20:00 scheduled brief now calls the brief contract before writing while
keeping its cloud sources, no-Nia, no-write, no-email, no-second-producer, and
natural-window-only proof boundaries. The app is private to Leo's ChatGPT
account. The unauthenticated Worker endpoint contains only the same public
static writing contracts checked into this repository; it contains no Shadow
board, plan, credentials, transcripts, storage, or mutation capability.
