# claudux — documentation preferences for Shadow

Read at generation time. Shadow's docs are a law surface, not marketing:
most pages under `docs/reference/` are contracts that code and tests pin.

## Hard protection

- NEVER reword, summarize, or restructure these files — they are frozen law
  whose exact phrasing is load-bearing (tests and scripts grep them):
  `docs/reference/grammar.md`, `docs/reference/privacy.md`,
  `docs/reference/slots.md`, `AGENT.md`, `SKILL.md`, `skills/goal/**`.
  Structure, navigation, and links may point AT them; their bodies are
  read-only.
- Never invent a verb, flag, or config key. The CLI surface is exactly what
  `bin/shadow` and `docs/reference/commands.md` state. If a page seems to be
  missing a command, that is a finding for a human, not a gap to fill.
- Never add a router, daemon, scheduler, cloud executor, credential relay,
  transcript store, or "memory" integration to any description. These are
  standing boundary nouns; their absence is the product.

## Voice

- Lead with what a reader can DO, then the contract. Benefit before mechanism.
- Short declarative sentences. No "seamless", "powerful", "robust",
  "comprehensive", "leverage", "supercharge", "beautiful", "transform".
- Six core nouns carry the system: board, plans, seats, claim, proof, accept.
  Introduce nothing else as if it were core.
- Code blocks must be copy-runnable on macOS/zsh with only a seat-name
  placeholder. Quote `~ab12` row ids (zsh expands bare tildes).

## Structure

- `docs/index.md` is a VitePress home page and stays one screen.
- `docs/guide/` = doing (install, first run, handoff). `docs/reference/` =
  law (verbs, grammar, slots, privacy). Do not blur the two.
- The README stays out of scope for claudux entirely.
- `docs/plan-archive/` and `docs/superpowers/` are historical record, not the
  docs site. Never rewrite, restructure, delete, or add nav entries for them.
  Only `docs/index.md`, `docs/guide/`, and `docs/reference/` are in scope.
