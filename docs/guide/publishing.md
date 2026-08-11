# Use Shadow in more places

Shadow has one local authority and several honest front doors. A new surface
must never pretend it can see current work when it cannot reach the computer's
board.

```mermaid
flowchart LR
    person["A person states intent"] --> surface["ChatGPT · Codex · Claude · Cursor"]
    surface --> brief["One human brief\noutcome · motion · consequence · confidence"]
    brief --> local["Local Shadow\none board · current product plans"]
    local --> proof["Proof or one clear restart condition"]
    proof --> brief
```

## What ships now

| Surface | What people get | Authority boundary |
| --- | --- | --- |
| ChatGPT and Codex | The `.codex-plugin` package and repo marketplace expose the same Shadow skill and goal shaper. | Full status and action require a local host that can read the board and run Shadow. A hosted chat is a coach only. |
| Claude Code | The existing `.claude-plugin` package installs the same source skill. | Local board access follows the existing install and host rules. |
| Cursor | The checked-in skill works through Cursor's local skill/plugin support. | Cursor can act only where the local checkout and host integration are available. |
| Private ChatGPT app | Leo's account connects to a reviewed, read-only MCP coach that returns the human brief and goal contracts. | It receives no local board, plan, credentials, or transcripts and has no mutation tools. Cloud apps supply facts; local Shadow remains authority. |
| Custom GPT | The skill prose can seed a friendly “Shadow Coach” for goal shaping and explanation. | A Custom GPT cannot see the local board and may use the private app only for the same read-only contracts. |
| MCP directories | The reviewed bridge is deliberately absent from every public directory. | Its endpoint contains only public static coaching contracts. Public submission remains a separately authorized release step. |

Install the repo marketplace locally for a dry run:

```bash
codex plugin marketplace add /path/to/shadow
codex plugin add shadow@shadow
```

The same public listing can later be submitted once to the universal ChatGPT
and Codex directory. Claude, Cursor, and MCP directories keep their own review
and publishing steps. Submitting any external listing is a publishing action and
remains a person-authorized release step.

## Cut one immutable source release

The ordinary package check is a development receipt and is never sufficient
to call moving `main` publishable. Public-release mode requires an annotated
tag named `shadow-v<version>` at exact `HEAD`; legacy `v*` tags belong to the
older numbering epoch and never satisfy this check.

```bash
git tag -a "shadow-v$(cat VERSION)" -m "Shadow $(cat VERSION)"
scripts/shadow-python.sh scripts/shadow-release-package.py \
  --public-release --expect-version "$(cat VERSION)" --json
```

The green receipt names the exact commit, namespaced release ref, and
reproducible archive SHA-256. Pushing that tag, creating a GitHub Release, and
marking it Latest remain separate publication/readback steps; none is inferred
from the local receipt. The README stable-install command must already name the
same immutable tag before the tag is published.

## The one human brief

Every surface should answer the same questions before it exposes machinery:

1. What are we trying to change for a person?
2. What is moving now, in parallel?
3. What changed, and why does it matter?
4. What is stalled, and what single condition restarts it?
5. What decision or attention is needed?
6. How confident is the read, and which evidence is missing?

Branches, hashes, repository state, row IDs, commands, and raw receipts belong
in technical evidence on demand. They are not the story of the work.

## First success for a nondeveloper

A first-time user should be able to paste a rough goal and receive a useful
outcome, a plain-language current-state explanation, and one next move without
knowing Git or Shadow's plan grammar. Writing to the real board still requires
the local product. The private ChatGPT bridge makes the writing contract
available remotely; it does not create a remote board, copy a plan, or return a
claim.

That split is deliberate: wide distribution may improve comprehension before
it earns remote authority, but it may never imply false parity.
