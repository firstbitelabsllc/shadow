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

There is no telemetry of any kind. Local receipts and Git history are the
only observation surfaces. Which provider or account a native host uses is
the host CLI's own business — Shadow passes no selector and records none.
