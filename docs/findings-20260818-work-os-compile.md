# Shadow core findings — 2026-08-18 work-os compile (work Mac)

Logged while compiling Leo's work-os entity on the work machine. Untracked on
purpose — commit/push is the owner's call. Each finding was hit live, not
theorized; receipts are on the work Mac's board (`~/.shadow`, revisions
349–354).

## 1. Completed-orphan claim has no cross-seat release path (highest value)

A `[completed]` row whose claim owner never ran `return` is permanently wedged:
`throw --adopt-expired` refuses completed rows, and `return --by` refuses any
seat but the owner. Live corpse: seat `codex` claimed `~mvp1` on the
emoji-search-tags entity 2026-08-13 (return_by 2026-08-13); five days later no
other seat can release it, and board-catchup's Deferred already documents the
dead end verbatim. Fix shape: a supported completed-orphan release —
release-with-receipt that requires the row be `[completed]` with its PROOF line
present, records which seat performed the release, and never forges the
original owner's tombstone.

## 2. Machine-local entities have no mint/registration path

`shadow init --here` exits 2 outside a Git project root, so an entity under
`~/.shadow/plans/<name>/` cannot be scaffolded by the CLI at all. A hand-written,
`shadow lint`-clean plan there is then invisible to `shadow status` — nothing
imports it. The only way it registers is as an undocumented side effect of the
first `shadow throw --repo <plan-dir> ...`. No help text (init, status, throw)
says claim-is-registration. Hit live: work-os was lint-clean and unrendered
until the first throw registered it at board revision 351. Fix shape:
`shadow init --local <name>` (scaffold + register), or a `register` verb, plus
one help-text sentence naming first-claim registration.

## 3. Throw packet advertises a nonexistent loop skill

The throw packet prints `Loop: /work-os-loop` for a Brief that declares no
`Loop:` line — the default projection `/<project>-loop` is emitted as if it
were a real invocable skill. A cold seat following the packet would try to
invoke a skill that does not exist on the machine. Fix shape: omit the Loop
line when no such skill resolves locally, or print it as
`Loop: none (convention /<project>-loop)`.

## 4. Migrated plan-trees strand read-proof flips

On a `shadow.plan-tree.v1` plan (emoji-search-tags), a `read`-proof row cannot
be flipped at all: `shadow accept` refuses read proofs by design ("person
judgments"), the AGENT.md instruction is "append the PROOF line with the flip"
— but the plan is a content-addressed object store with no append verb — and
`shadow plan rollback --expect <sha>` answers "plan root changed before
rollback" for both the `logical_sha256` and `catalog_root` digests the plan
header itself displays. Hit live 2026-08-18 completing `~mvp2`: the proof
artifact satisfies every clause, and there is no supported way to record the
flip. Fix shape: a `shadow plan append-progress` / person-flip verb for
migrated plans, or rollback accepting the digests the header actually prints.

## 5. Discovery has no per-repo opt-out

Bounded discovery imports every portfolio-root child owning a root PLAN.md —
correct as a default, but there is no way to keep one repo OFF a machine's
board. Hit live: the personal `trysnowcubes-web` clone sits in the work Mac's
`~/Snapchat/Dev`, so it auto-boarded on 2026-08-14 and its stale personal-seat
claim kept surfacing in work sweeps. `shadow priority --value 5` only re-ranks
it; it still renders and its claims still list. The only real escapes are
moving the checkout out of the portfolio root (which breaks the registered
locator and strands existing claims) or deleting the plan. Fix shape: an
`ignore` list in the root board, or a `- Board: none` Brief line honored by
import, either of which must still name the exclusion in `shadow status
--shadowed` so nothing disappears silently.
