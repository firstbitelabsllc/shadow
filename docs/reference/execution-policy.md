# Native execution policy

Shadow used to seal a task to a native host while leaving that host's model
entirely implicit. That was safe for credentials, but it made a claimed model
roster impossible to prove: choosing `codex` did not prove Sol, choosing
`claude-code` did not prove Fable or Opus, and a successful receipt carried no
evidence that the intended capability or cost tier ran.

The replacement is deliberately small. The driving lead chooses a native host,
one semantic work class, and whether the packet is `direct` or requires one
native child. Shadow resolves the host/class pair to the native `--model`
selector and configures the declared execution shape:

| Work class | Claude Code | Codex | Cursor | Grok |
| --- | --- | --- | --- | --- |
| `planning` | Fable | Sol | Fable High | Grok 4.6 |
| `coding` | Opus | Sol | Opus High | Grok 4.6 |
| `review` | Fable | Terra | Cursor Grok 4.6 High | Grok 4.6 |
| `lightweight` | Sonnet | Luna | Auto | Grok 4.5 |

Use it through the one sealed door:

```bash
shadow host run --host codex --work-class coding --delegation direct \
  --repo /absolute/clean/worktree --task-file /absolute/frozen-task.txt \
  --task-id add-proof --allowed-path src/proof.py \
  --out /absolute/project/.shadow/evidence/add-proof.json
```

The policy does not inspect prompt text, choose an account, retry another
provider, or silently downgrade after a quota error. Unsupported models,
authentication failures, and exhausted quota stay explicit failures for the
lead to record with one wake. Cursor `Auto` is intentionally named as an
opaque provider selector: the CLI can prove that Auto was requested and
reported, but not which underlying model Cursor chose.

Delegation is a separate dimension because task difficulty and worker topology
are not the same decision:

| Shape | Contract |
| --- | --- |
| `direct` | Disable native child spawning where the CLI exposes a control; do the bounded packet in the parent. |
| `required` | Enable and explicitly require one native child evidence lane. Claude Code uses `Agent`, Codex enables `multi_agent`, and Grok uses `spawn_subagent`. |

Cursor currently fails closed for `required`: its headless CLI exposes no
verified structured child-lineage contract. The wake is a Cursor CLI capability
that produces observable native child lineage. Shadow does not emulate that
capability with a hidden second process and then call it native delegation.

The private host-attempt receipt records the work class and requested model.
It does not claim an observed model. A selector proves an instruction, not
provider execution; observed-model proof requires the owner-local gauntlet
below. Account, session, billing, raw prompt, transcript, and provider payload
remain excluded.

## The ten failures this closes

1. **A host name was mistaken for a model decision.** That made every roster
   claim unverifiable and allowed defaults to drift unnoticed.
2. **Requested and observed models were conflated.** A command-line selector
   can be ignored, aliased, or resolved to a different label.
3. **Helper and parent models were conflated.** One Claude run may report
   parent and helper usage; the parent init record is the routing witness.
4. **Opaque fallbacks looked precise.** Cursor Auto is useful, but it does not
   reveal the underlying model and must be described that way.
5. **Static command tests stood in for real execution.** They cannot prove
   authentication, quota, tool use, edits, or provider response.
6. **Delivery was treated as observability.** An OTLP request returning without
   an exact Langfuse readback is not a stored trace.
7. **Delegation prose stood in for delegation.** A scenario that requires a
   child passes only with a native child-tool lineage record; the source policy
   now declares `direct` or `required` instead of hoping the prompt delegates.
8. **A process exit stood in for completion.** Every run also needs the exact
   changed paths, a fresh deterministic verifier, and a terminal completion
   token in the model's final response.
9. **Capability and quota failures had no stable wake.** Unavailable auth,
   model, quota, or child capability is red or `UNKNOWN`, never a guessed pass.
10. **Source, merge, install, and live use collapsed into one green check.**
    The gauntlet proves source behavior only; release and dogfood need their
    own receipts.

These failures matter because a cheap-model roster is valuable only if it
actually saves scarce reasoning while preserving hard-work quality. An
unobserved router can do the opposite: spend frontier quota on trivial work,
send hard work to a weak tier, and still report success.

## Owner-local 12 by 4 gauntlet

`scripts/dev/shadow-routing-gauntlet.py` expands twelve checked-in scenarios
across Claude Code, Codex, Cursor, and Grok: 48 real headless CLI jobs. The
fixtures cover contradiction resolution, architecture, implementation,
debugging, adversarial review, concise summaries, documentation repair,
false-green rejection, cold resume, native-child lineage, protected wakes,
and a planted completion-token trap.

Each terminal row is green only when all of these are true:

- the process exits zero before its timeout;
- the requested selector matches the checked-in policy;
- structured native output, or Codex native OpenTelemetry spans, reports a
  matching observed model;
- structured usage is present;
- changed paths equal the scenario allowlist;
- a fresh deterministic verifier passes;
- the exact completion token appears in the final model response, not merely
  in an echoed prompt;
- a required native child leaves structured lineage;
- an allowlisted red provisional span is accepted by local Langfuse;
- the exact trace ID is subsequently readable from Langfuse's event store; and
- only after that readback does the same trace receive its final adjudication.

If readback fails, the trace retains only the red non-final span. This ordering
prevents accepted-but-unreadable telemetry from leaving a contradictory green
record in Langfuse.

The mutation suite independently turns each predicate false and requires the
grader to reject it. The gauntlet stores no raw prompt or transcript in
Langfuse. It sends bounded scenario, host, requested/observed model, terminal
state, usage, cost when supplied, child count, and pass/fail facts. The gauntlet
refuses non-loopback Langfuse and readback URLs. The local Langfuse instance is
evaluation tooling only: it never chooses a route, owns a
claim, accepts a checkpoint, or ships with Shadow.

The gauntlet intentionally exits non-zero when any row is red while still
writing all terminal results to its JSON summary. That makes provider limits
and unsupported child capabilities inspectable without letting a partial
matrix disappear.

## Why there is no automatic hidden router

The old alternative was a large prompt classifier and roster that guessed a
host, account, model, fallback, and worker topology. It duplicated native CLI
configuration, hid quota-driven drift, and created a second scheduling system
beside the Shadow board.

The four work classes and the explicit execution shape are the whole product
policy. The lead still chooses the host because host capability, custody,
quota, and current authorization are live operational facts. Shadow selects
the model deterministically once that choice is made and fails closed if the
pair or required child capability cannot run. More automation can be added only
after it has a native capability receipt and does not create a new authority,
queue, credential relay, or silent fallback.

The dated [four-host evidence and cold takeover](execution-policy-evidence-2026-08-26.md)
records the exact 48-row baseline, correction runs, hashes, failures, and next
overnight checkpoints.
