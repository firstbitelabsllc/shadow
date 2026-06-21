import { defineAgent } from "eve";

export default defineAgent({
  description:
    "Read-only Resplit Eve onboarding specialist for iOS, web, currency API, skill-port, and proof-ladder routing.",
  model: process.env.EVE_MODEL ?? "anthropic/claude-sonnet-4.6",
});
