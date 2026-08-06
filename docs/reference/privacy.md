# Privacy

Shadow stores only bounded semantic receipts. It rejects or omits:

- credentials and secret-shaped values;
- raw prompts, conversations, and provider payloads;
- absolute home or machine-specific paths;
- provider account, model, session, and billing data; and
- arbitrary commands in public receipts.

Native-host receipts also use a closed `tests` shape — each entry carries
exactly `name` and a `status` of `pass` or `fail`, with a bound test-name
length and the same secret/path checks before it is written under
`.shadow/evidence/`.

The browser is loopback-only. Evidence stays inside the Git project under
`.shadow/evidence/`. There is no remote authority, cloud executor,
credential relay, watcher, daemon, background dispatch process, or transcript
store.

Langfuse observation is optional and off by default. When an operator
explicitly configures `SHADOW_TELEMETRY=langfuse` and a Langfuse endpoint,
Shadow may export a metadata-only lifecycle event only *after* the local
route or host receipt has been written. It is never read back, cannot route,
launch, retry, accept, merge, or change an exit code, and a missing SDK,
configuration, or remote failure is ignored locally. Use an explicitly chosen
self-hosted endpoint; Shadow has no implicit cloud destination.

Those events have a closed schema: random future Drive session/lane IDs,
generic role and host family, terminal state, coarse duration bucket, lane and
allowed-path counts, and nullable scope/proof/merge booleans. They never carry
task IDs or text, plans, prompts, chats, source code, diffs, file names or
paths, commands, receipt contents, provider payloads, models, accounts,
quotas, costs, credentials, browser decisions, PR links, or raw errors.
Langfuse input and output are always `null`; Shadow does not use Langfuse
prompt management, datasets, evaluations, webhooks, or LLM tracing.

`shadow roster` is separate local setup data. It is not a project
authority or receipt, and `browse` and `status` never read it. Keep named-seat
details private; Shadow does not store provider, model, account, or quota
data in browser output, status output, or receipts.

`shadow route` may write a small project evidence packet, but that packet
contains only generic roles, native-host surfaces, bounded state, and hashes.
It excludes roster slot IDs, task text, local paths, model/account/quota data,
commands, credentials, provider payloads, and transcripts.
