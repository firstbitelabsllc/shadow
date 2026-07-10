# Releasability decision packet (maintainer-gated)

Date: 2026-07-10. Written after panel round 11 (12/20 GO).

Every fixable finding from rounds 1–11 has been shipped. What remains between
here and "publicly releasable" is **not** more engineering — it is two
decisions only the maintainer can make, because both items are exposed *only*
when GitHub repo visibility flips from private to public, and that flip is a
hard rail no agent performs unilaterally.

This packet states each decision, a recommendation, the default if nothing is
decided, and the consequence of each option. It describes sensitive content by
class, never by literal string (the same describe-don't-quote rule the panel
enforces).

## Where things stand

- **npm package layer: clean.** The published tarball is reproducible, excludes
  `evidence/`, tests, tokens, and (as of round 11) the private "Eve cockpit"
  tree and the private-fleet integration scripts. A consumer `npm install`
  exposes none of the items below.
- **GitHub visibility layer: gated.** Flipping the repo public exposes the full
  git history and the GitHub-server-maintained PR refs, plus every tracked file.
  The two decisions below live entirely at this layer.

These are different layers, not a contradiction: package-clean ≠ history-clean.

## Decision 1 — git history

Two classes of sensitive content sit in git history / PR refs, invisible to the
text scanners by design (they scan working-tree file *content*, not commit
messages or server-side refs):

1. **An internal employer ML-infra endpoint** in one commit's *message*. That
   commit is not on `main`, but it is permanently reachable from five
   GitHub-maintained `refs/pull/*/head` PR refs, which survive any `main`
   rewrite and are fetchable by anyone with repo read access. The same
   endpoint-shaped string also sits in two `main`-reachable commits (a round-9
   grep-gate test fixture that used the real string instead of a synthetic one;
   the working file is clean now, the historical blobs are not).
2. **Employer-machine identity** (a work-laptop home path, an employer-tied
   handle, an internal codename) in exactly four commit *messages* reachable
   from `main`.

Root property: both persist in server-side PR refs that a `main` history rewrite
does **not** touch. So the reliable options are limited.

**Options:**
- **(A) Recreate the repo from the clean current tree** — new repo (or fresh
  root), push the current clean state, abandon the old commit/PR history.
  *Consequence:* fully purges both classes (no PR refs, no old messages); loses
  the public commit history and the existing PR threads. The most reliable purge.
- **(B) Rewrite `main` history + ask GitHub Support to purge the PR refs** —
  `filter-repo` the four messages + the two fixture commits, force-push, and
  open a support request for the five PR refs. *Consequence:* keeps most
  history; force-push rewrites ~789 commits; the PR-ref purge is
  support-dependent and not guaranteed.
- **(C) Accept and flip anyway** — judge the leaked strings (an internal
  hostname + machine identifiers, no credentials/customer data) low-consequence
  enough to publish. *Consequence:* immediate unblock; the strings are public.
- **(D) Stay private** — no action; the releasability work is "ready when you
  decide."

**Recommendation:** (A) recreate-clean if you want zero residual, since it is
the only option that reliably clears the PR refs; (C) is defensible only if you
personally judge the specific internal-hostname/machine-identifier strings
acceptable to expose. I would not do (B) alone — the PR-ref purge is too
uncertain to rely on.

**Default if you say nothing:** repo stays private (D). Nothing is rewritten,
recreated, or exposed.

## Decision 2 — private cross-business content scope

Beyond the PNG PII (already removed in round 11) and the Eve cockpit + fleet
scripts (already excluded from the npm package in round 11), the git *tree*
still carries references to the maintainer's other private products across
several docs and one script (`scripts/vidux-fleet-rebuild.sh`, which also
contains real automation-lane IDs and a private DB path, and is woven into the
docs + a lib script). The panel has flagged this "private-fleet content" class
across four rounds and each time deferred it as the maintainer's disclosure-
preference call.

**Options:**
- **(A) Scrub the tree** — genericize/remove the cross-product references and
  `vidux-fleet-rebuild.sh`, then add scanner rules so the class can't recur.
  *Consequence:* clean public tree; some real integration scripts lose their
  concrete fleet detail (you keep local copies).
- **(B) Exclude from package, leave in tree** — the round-11 posture: the
  private content doesn't ship in `npm`, but is visible on a public-visibility
  flip. *Consequence:* fine while private; needs revisiting before going public.
- **(C) Leave as-is** — accept the cross-product references as acceptable
  disclosure. *Consequence:* no work; the references are public on flip.

**Recommendation:** (A) scrub before any public flip — it pairs naturally with
whichever git-history option you pick in Decision 1 (a recreate-clean pass is
the moment to scrub the tree too). Until a flip is on the table, (B) is a fine
holding state.

**Default if you say nothing:** (B) — the round-11 exclusion holds; nothing is
scrubbed or deleted from the tree.

## Not blocking (informational)

- The SKILL.md information-architecture question (advanced concepts before the
  foundational ones for a cold reader) remains a positioning judgment call, not
  a defect — noted for you, not acted on.
- The earlier "warm paper vs cool near-white" palette tension resolved itself:
  the concurrent lane's rebrand already moved the shipped palette to the cool
  near-white the design binding prescribes.

## One-word replies that move this forward

- Decision 1: `recreate` / `rewrite` / `accept` / `private`.
- Decision 2: `scrub` / `exclude` / `leave`.
