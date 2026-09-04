# Worktree Lifecycle + Plan Tree Design

**Status:** Approved by Leo on 2026-09-03. This document freezes the user directive recorded as Shadow milestone M41 (`~wl01`–`~wl07`).

## Goal

Ship one conservative `shadow clean` door and one read-only Tree view so a person can understand where work lives and retire finished Shadow-managed worktrees without supervising Git archaeology. Cleanup is recoverable, exact, and opt-in. The private computer board and canonical entity plans remain the only work authority.

## Non-goals

- No `/purge`, global scavenger, permanent deletion, `rm -rf`, forced Git removal, daemon, watcher, scheduler, or background polling loop.
- No adoption, registration, or inference of pre-existing worktrees by path, directory name, branch name, repository name, or proximity to another checkout.
- No cleanup of any worktree that existed before this implementation began.
- No new task database or GUI-owned state. The Tree view cannot mutate a plan, claim, proof, wake, worktree, or cleanup preference.
- No claim that moving bytes to Trash removes Git's administrative registration. Recoverability deliberately keeps that registration locked until restoration or a separately authorized future finalization.
- No publication, install, or live-machine automatic-cleanup opt-in during implementation.

## Existing owners to reuse

- `scripts/shadow-lifecycle.py` already owns strict retirement manifests, clean-tree checks including ignored files, landed-ref ancestry, linked-versus-primary worktree checks, submodule and symlink refusals, exact inode/device/head/status/listing CAS, project locking, crash journals, and path-free committed retirement receipts.
- `scripts/shadow_root_board.py` already owns canonical entity pointers, claims, owners, resume, project priority, public plan locators, and atomic board reads.
- `scripts/shadow-amp.py` already parses milestones, checkpoint fields, dependencies, proof classes, blocked wakes, and reachability from canonical plans.
- `browser/server.py` already joins the root board to canonical plan projections and projects milestones/checkpoints. `browser/static/app.js` already renders read-only board data with text nodes.

The implementation extends these owners. It does not create a parallel scanner, parser, or status ledger.

## Worktree provenance

Eligibility begins with an immutable machine-local creation receipt. It is written only by Shadow's managed-worktree creation primitive at the same time that primitive successfully runs `git worktree add`. A worktree found by scanning Git, the filesystem, or an old branch is not Shadow-created and is ineligible.

The receipt is stored below the computer's private Shadow root, never in the product repository. It binds:

- schema and creation timestamp;
- exact canonical worktree path, device, and inode;
- exact Git common directory and worktree administrative directory;
- source repository identity;
- entity id, checkpoint id, creating seat, initial HEAD, branch or detached state, and intended landed ref;
- a canonical receipt digest.

The file is created with exclusive, no-follow semantics and mode `0600`; an existing or changed receipt is refused. Public output exposes only an opaque `worktree@<digest-prefix>` identity and lifecycle state. It never prints the path, Git ref, process command, or raw receipt.

The first release wires the primitive to a narrow `shadow clean --create` operation for future managed lanes. It requires an already-live exact entity/checkpoint/seat claim, an absent absolute destination, a safe branch/ref, and a source checkout sharing the entity's declared source identity. This is the only supported way for a general development worktree to gain cleanup eligibility. Existing worktrees cannot be retroactively blessed.

## `shadow clean` contract

### Preview is the default

`shadow clean [--repo PATH] [--worktree /ABS/PATH] [--json]` writes no repository, board, plan, Git, worktree, preference, or Trash state. It enumerates only valid Shadow creation receipts, optionally narrowed to one exact worktree, and explains every candidate or refusal.

For an eligible candidate, preview writes one fresh private retirement manifest only when the operator passes `--manifest-out /ABS/PATH`; automatic lifecycle cleanup uses the same in-memory generator. The generated manifest binds the creation receipt, entity/checkpoint, target HEAD, landed ref, generation time, short expiry, and the lifecycle retirement target. Preview then runs the shared retirement inspector and returns its exact CAS. A user-authored, expired, changed, symlinked, non-regular, or non-Shadow manifest never applies.

Human text leads with the reason: `eligible`, `checkpoint is not terminal`, `work is not landed`, `worktree is dirty`, `untracked files exist`, `ignored files exist`, `active claim`, `process holds worktree`, `primary worktree`, `not Shadow-created`, `symlink`, `submodule`, `manifest expired`, or `changed since preview`.

### Apply moves to Trash

`shadow clean --apply --manifest /ABS/PATH --expect CAS --by SEAT` requires the fresh clean manifest and exact preview CAS. Under the existing project lock it re-runs every predicate, rechecks the manifest expiry and creation receipt, and compares the target's path/device/inode/HEAD/status/Git listing with the preview.

Immediately before mutation it checks again that:

1. the associated canonical checkpoint is terminal (`completed` or `blocked`);
2. no computer-board claim names that entity/checkpoint;
3. the target HEAD is an ancestor of the declared landed ref;
4. tracked, staged, untracked, ignored, and submodule state are absent;
5. no live process has its current directory or an open file below the target;
6. the target is a real registered linked worktree, never the primary worktree or a symlink;
7. the target and fresh manifest are unchanged.

Process inspection uses `/proc/<pid>/cwd` and file descriptors where available, and the operating system's bounded `lsof` interface on macOS. If Shadow cannot prove the process boundary, cleanup refuses.

The worktree is first locked with a digest-bound Shadow Trash reason. Shadow then atomically renames the exact directory into the real per-user OS Trash on the same device. Cross-device copy-and-delete is forbidden. It does **not** run `git worktree remove`, `git worktree prune`, or any force flag. The locked Git registration and a private crash-safe Trash receipt preserve the exact original and Trash locations, device/inode, creation receipt, and CAS. The existing public retirement receipt remains path-free.

### Restore proves recovery

`shadow clean --restore --manifest /ABS/PATH --expect CAS` is the inverse of a completed Trash move. It requires the exact private Trash receipt, an absent original destination, the same Trash inode/device, and the same locked Git worktree registration. It atomically renames the directory back to its original path, verifies HEAD and cleanliness, unlocks the registration, and marks the private receipt restored. Any collision or mismatch refuses without moving either path.

This proves recoverable cleanup rather than merely proving that a file exists somewhere in Trash.

## Automatic cleanup

Automatic Trash is disabled by default. `shadow clean --auto enable|disable|status` owns one strict, mode-`0600`, machine-local preference below `~/.shadow`; it stores only `{schema, automatic_trash}` and is not work authority.

The only automatic call site is the end of a successful existing lifecycle mutation/acceptance boundary, after authoritative work state is durable. It performs the same preview, creates a fresh manifest, and calls the same apply transaction. It never runs on a timer, host launcher, status read, browser refresh, install, or cold start.

Automatic cleanup scans only immutable Shadow creation receipts. An ineligible candidate is reported in the lifecycle result and left untouched; one refusal cannot broaden eligibility or trigger a retry loop. The currently executing worktree is process-held and therefore refuses naturally.

## Tree projection

`GET /api/plans` keeps its existing `plans` payload and adds a `tree` projection:

```text
computer
└── project
    └── entity
        └── milestone
            └── checkpoint
```

- Computer: opaque computer identity and board revision.
- Project: project id/name and board priority.
- Entity: opaque entity id, public source-plan locator, integrity state, and resume checkpoint.
- Milestone: sanitized title, counts, current state, and owners.
- Checkpoint: state, availability, owners, sanitized proof class/text, sanitized wake, and associated worktree lifecycle summaries.

The server builds this from the already-read root-board payload, the canonical entity plans, and sanitized Shadow worktree creation/Trash receipts. It does not rescan provider chats, create another endpoint, or persist its projection. Absolute paths, secret shapes, raw manifests, Git OIDs/refs, commands from live processes, and private receipt contents are withheld. “Withheld” is preferable to partial redaction when a field cannot be shown safely.

The browser adds one `Tree` view beside the existing views. Native `<details>/<summary>` elements provide keyboard expansion and collapse. The surface preserves existing system typography, restrained colors, focus rings, empty/unavailable teaching states, responsive layout, text-node rendering, loopback-only server, CSP, and read-only behavior.

## Refusal and proof matrix

All tests use temporary repositories, isolated `HOME`, and a test Trash directory on the same filesystem. No existing developer worktree is a fixture.

| Case | Required result |
|---|---|
| Primary worktree | Refuse; target and registration unchanged |
| Tracked/staged dirty | Refuse; bytes unchanged |
| Untracked file | Refuse; file preserved |
| Ignored file | Refuse; file preserved |
| HEAD not in landed ref | Refuse |
| Associated active claim | Refuse |
| Process current directory/open file below target | Refuse |
| Symlinked target or path component | Refuse |
| Submodule present | Refuse |
| Missing/forged creation receipt | Refuse as not Shadow-created |
| Expired or changed manifest | Refuse as stale |
| Target changes after preview | Refuse by CAS |
| Eligible default invocation | Explain only; zero mutation |
| Eligible apply | Same inode moves to Trash; no hard-delete/prune/force |
| Restore | Same inode returns, Git registration unlocks and works |
| Auto disabled | Lifecycle boundary leaves target untouched |
| Auto enabled | Boundary invokes the same preview/apply once |
| Tree payload | Exact hierarchy and required safe fields |
| Tree UI | Keyboard-accessible expansion and responsive rendering |
| Stranger install | Installed archive exposes `shadow clean`; doctor and focused proofs pass |

## Completion boundary

M41 is complete only when one reviewed source SHA has focused and full test receipts, the refusal matrix, Trash move-and-restore proof, disabled/enabled lifecycle-boundary proof, Tree payload and DOM proof, package digest, stranger installation, and a before/after inventory demonstrating that no pre-existing worktree was cleaned. Merge, install, and live opt-in remain separate receipts; implementation does not enable automatic cleanup on Leo's computer.
