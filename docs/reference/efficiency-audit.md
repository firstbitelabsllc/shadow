# On-demand roster evidence inventory

Run this with Python 3.10+ from a pinned Shadow checkout in any terminal host:

```sh
python3 -m unittest tests.test_efficiency_audit
python3 scripts/dev/shadow-efficiency-audit.py --help
python3 scripts/dev/shadow-efficiency-audit.py --source codex=/absolute/canonical/session.jsonl
python3 scripts/dev/shadow-efficiency-audit.py --source claude=/absolute/canonical/session.jsonl --since 2026-09-01T00:00:00Z --until 2026-09-02T00:00:00Z
```

Repeat `--source` to compare selected source coverage. Each input must be one
native session's UTF-8 JSONL recording. The harness is caller-declared, not
attested. Explicit canonical paths are required: leaf and ancestor symlinks
refuse, including macOS `/var` aliases (use their `/private/var` path). The
command performs no discovery, provider call, network request, source write,
sink export, board mutation or acceptance. It prints JSON to stdout. If saving
a private report, use an existing private directory and `umask 077` first.

The `shadow.efficiency-inventory.v1` report is a projection of selected evidence,
never an authority or a complete account-usage report. Its source hashes bind
the bytes read; the paths, native session/message IDs and message bodies are
not exported. A source that changes during the read refuses. The command limits
input to 64 sources, 64 MiB in aggregate and 1 MiB per line. Malformed, non-object,
overlarge, unreadable or symlink input refuses the whole report with a fixed
reason code and exit 2; it never silently skips a damaged tail. Empty session
files remain explicit missing-usage records.

## What the inventory establishes

| Input | Evidence used | Limit |
| --- | --- | --- |
| Codex / Codex-ZAI | Session identity, requested `turn_context.model`, cumulative `token_count` usage | Context model is not a native response model. No provider attestation. |
| Claude | Native assistant message ID, response model label and per-message usage | Duplicate message updates count once; label is not independently authenticated provider identity. |
| Grok | File fingerprint and explicit unsupported-adapter gap | No model, usage or delegation inferred from generic tool events. |
| Cursor / ZCode / OpenCode | No adapter in this version | `unsupported_harness`; run the command from those hosts, but do not claim it collected their activity. |

This is **portable execution, not complete cross-host collection**. Known future
work belongs in the existing owning plan, not in a new router, diary or database.

`sessions_with_input_output_counters` means valid input/output counters, not that every cache
or reasoning field is known. Each absent counter remains null. Codex input can
include cached input and output can include reasoning; do not add those subsets
again. Claude cache counters are separate native fields. The inventory does not
sum incompatible bases into one headline total or allocate session totals among
multiple models. It reports session counts, not attempts or useful task counts.

Identical source bytes under one declared harness are deduplicated. Different
copies with the same native session identity are marked conflicting and usage
becomes unknown. Counter resets, decreasing message usage, mixed session IDs,
missing identities and unknown wire shapes also stay explicit. Child metadata
is not proof of a canonical parent/child task join.

Windows are inclusive `--since`, exclusive `--until`, and timezone-aware.
An until-only query returns cumulative usage through that cutoff, not an interval delta.
Codex cumulative window usage requires a pre-window baseline; otherwise it is
unknown, even if a plausible zero baseline could be guessed. All windowed
sessions carry `partial_window=true`. Source/record counts describe the full
selected files, not just in-window events. No window duration is attention or
billable compute. Selected files are not a representative sample.

## What remains unmeasured

The following are deliberately null: real-work allocation, accepted-work rate,
accepted root task, confirmed delegation, cost and Leo attention. There is no
native-attempt-to-canonical-task/acceptance join in this command yet. A success
string, exit status, configured model, claim, trace ID or Langfuse write cannot
populate those values. Neither this CLI nor a green test proves a collector,
live sink, normal-work baseline, quality comparison or automatic routing.

Next integration must bind real native run/handoff IDs to existing canonical
entity/checkpoint acceptance, distinguish retry from root outcome, and refuse
a forged or uncorrelated binding. Use existing Shadow readers and receipts.
Keep requested identity, native label and provider attestation separate. Only
after that join and exact approved local trace readback should the owning
observation protocol start its comparison window. Do not add a second ledger,
watchdog, hook, scheduler or skill to implement resume.
