# "vidux" naming-collision check (2026-07-09)

Round-2 20-agent readiness panel flagged a `vidux.ai` naming-collision risk
as a P2 item. Researched it directly (web search) rather than leave it as
an unverified "risk" note.

## What exists under the name "Vidux" today

- **vidux.ai** — a live, actively-marketed "Professional AI Video Generator
  & Processing Tools" product. Same general category (AI/software tooling),
  different function (video generation vs. plan-first coding orchestration).
  This is the real collision: same word, same broad space (AI software),
  will compete for search/mindshare if this repo goes public under the name
  "vidux."
- **Vidux Kft** (Hungary) — a security-systems company; sells network video
  recorders and IP cameras under the "Vidux" brand (e.g. listed as a device
  brand in Luxriot Evo's supported-device catalog). Different industry
  (physical security hardware), lower practical collision risk.
- **Vidux®** — a Teknor Apex polymer material tradename. Different industry
  (materials/manufacturing) entirely; trademark classes for goods like this
  essentially never overlap with software, so legal risk here reads as low.

## What this does NOT resolve

This is a naming/positioning decision, not a code defect — I did not rename
anything (CLI binary `vidux`, npm package name, GitHub org/repo `firstbitelabsllc/vidux`,
or any doc). A rename is a wide-blast-radius, largely-irreversible-once-public
call that belongs to Leo, not something to force through under a "keep
shipping" mandate. Flagging cleanly here so it doesn't get lost, rather than
picking a side.

The real question for Leo: does `vidux.ai` (live AI video product, same
category) read as a blocking collision worth a rename before going public,
or an acceptable/ignorable coincidence given this repo's `firstbitelabsllc`
GitHub namespace and no domain-name ambitions? No code or doc change made
pending that call.
