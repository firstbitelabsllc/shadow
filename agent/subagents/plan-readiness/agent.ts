import { defineAgent } from "eve";

export default defineAgent({
  description:
    "Review Vidux plan, ledger, worktree, and public-ready proof readiness without mutating source, credentials, config, or external systems.",
  model: process.env.EVE_MODEL ?? "anthropic/claude-sonnet-4.6",
});
