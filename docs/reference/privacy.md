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

The private per-computer board must store absolute canonical entity pointers so
local commands can dereference them without guessing. `~/.shadow` is mode 0700,
`board.json` is mode 0600, those paths never enter public locators or portable
receipts, and the browser emits only scrubbed logical entity identifiers.

The browser is loopback-only. Evidence stays inside the Git project under
`.shadow/evidence/`. There is no remote authority, cloud executor,
credential relay, watcher, daemon, background dispatch process, or transcript
store.

There is no telemetry of any kind. Local receipts and Git history are the
only observation surfaces. Which provider or account a native host uses is
the host CLI's own business — Shadow passes no selector and records none.
