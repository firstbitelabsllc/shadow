# Grok Bot setup — from installed app to working chief of staff

State 2026-08-14: `/Applications/Grok Bot.app` 0.20.0 installed via
`brew install --cask grok-bot` (cask verified: homepage `x.ai/bot`, artifact
`downloads.cursor.com/sand/stable/darwin-arm64/0.20.0/Grok_Bot_0.20.0.dmg` —
xAI×Cursor launch, 2026-08-11). Everything below the login line is paste-ready.

## Leo (once)

1. Open **Grok Bot.app** → sign in. Access needs **SuperGrok Heavy, Cursor
   Ultra, or Cursor Teams Premium** — use the Cursor identity if it holds one
   of those tiers.
2. That is the whole gate. Stop here and any agent (or you) can finish the rest.

## Then, in the app

3. **Create bot "Shadow"** → paste `BOT-INSTRUCTION.md` (sibling file) as the
   first DM.
4. **Sign the bot's computer into GitHub** (bots have their own VM browser —
   the login happens inside the bot's screen, Leo typing): grant read of
   `firstbitelabsllc/shadow`. This is its only durable Shadow source.
5. **DMs**: the Shadow DM from step 3 is the daily surface. Test with an
   uncoached "what am I working on right now" — the repo carries method only,
   never live board state, so a correct answer REQUIRES a board paste: the bot
   must ask for one (then Leo pastes `shadow status` output and the answer
   works from it). A confident answer with no paste is the failure mode;
   correct it by re-pasting the instruction's Authority block.
6. **Group chat**: create **Shadow HQ** with Leo + Shadow. Add worker bots
   only when a real lane needs one (e.g. a Snowcubes ops bot); each new bot
   gets its own instruction file in this directory first, so the text is
   reviewed before it runs.
7. **Optional — MCP, only after PR #428 lands**: that PR carries the
   read-only coach endpoint (static brief/goal contracts, no board data);
   until it is merged the URL has no checked-in contract, so skip this step
   entirely. The GitHub read carries the port on its own.

## Boundaries that survive the port

- The board on Leo's Mac remains the only authority; the bot is a projection.
- No credential relay: every sign-in happens on the bot's own screen or Leo's.
- External sends (mail, posts, money) stay per-conversation Leo approvals.
- If the bot starts keeping its own queue, that is the #428 lesson repeating:
  delete the queue, restate Authority, re-test step 5.
