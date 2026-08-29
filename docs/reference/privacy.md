# Privacy

Shadow's public output and portable receipts expose only bounded semantic
state. They reject or omit:

- credentials and secret-shaped values;
- raw prompts, conversations, and provider payloads;
- absolute home or machine-specific paths;
- provider account, model, session, and billing data; and
- arbitrary commands in public receipts.

Native-host receipts also use a closed `tests` shape — each entry carries
exactly `name` and a `status` of `pass` or `fail`, with a bound test-name
length and the same secret/path checks before it is written under
`.shadow/evidence/`.

The two-seat verification receipt is also closed. It contains only its schema,
offline/live status, the shared goal SHA-256 and fetched source ref, stable
public seat completion booleans, bounded board revision/count facts, and one
fixed failure code or `null`. It never contains a temporary or operator path,
row prose, the goal text, prompts, transcripts, host diagnostics, or provider,
account, model, session, and billing data.

The optional remote coordination journal is a bounded Git object, not a task
payload. Its persisted `claim.json` fields are exactly `schema`, `state`,
`reason`, `entity`, `row`, `owner`, `project`, `plan`, and `claim`. `plan` is
closed to `head`, `blob`, and repository-relative `relative`; `claim` is closed
to `claimed_at`, `return_by`, and the fixed `recovery` action. The transient
public command outcome adds only `status`, `ref`, `winner`, and `failure`; those
four fields are not persisted in `claim.json`. Neither shape contains task
text, proof command or output, Progress prose, absolute or operator path,
environment value, credential, remote URL, or provider data. Public claim verbs
retain the journal's append-only acquired, released, and completed history;
they do not delete and recreate the ref.

The private per-computer board must store absolute canonical entity pointers so
local commands can dereference them without guessing. `~/.shadow` is mode 0700,
`board.json` is mode 0600, those paths never enter public locators or portable
receipts, and the browser emits only scrubbed logical entity identifiers.

The browser is loopback-only. Evidence stays inside the Git project under
`.shadow/evidence/`. There is no remote task or proof authority, cloud
executor, credential relay, watcher, daemon, background dispatch process, or
transcript store. When the current branch tracks a remote branch, the one
deterministic claim ref on that same tracked remote is only a coordination
lock; no other remote store or service is introduced.

There is no remote telemetry transport. Shadow has a closed [local event
vocabulary](telemetry.md). An explicit local-only opt-in may append the closed
event beneath the current project's `.shadow/evidence/`; it contains no plan
payload, proof output, environment, provider/account data, or operator path and
is never authority. The optional Git coordination lock carries no telemetry;
local receipts and Git history remain the only durable work/proof surfaces.
Shadow supplies the non-secret model selector from the chosen native host and
semantic work class, configures the explicit `direct|required` shape, then
records those requests in the private attempt receipt. It never records an
account, credential, session, billing identifier, prompt, transcript, or
provider payload. The product receipt does not infer an observed model or child
spawn from a request. Observed-model, child-lineage, and usage evidence belongs
only to the owner's local evaluation gauntlet; its bounded Langfuse summary is
not a portable receipt or product authority.
