# Privacy

Pilot Puppy stores only bounded semantic receipts. It rejects or omits:

- credentials and secret-shaped values;
- raw prompts, conversations, and provider payloads;
- absolute home or machine-specific paths;
- provider account, model, session, and billing data; and
- arbitrary commands in public receipts.

The browser is loopback-only. Evidence stays inside the Git project under
`.pilot-puppy/evidence/`. There is no remote database, cloud executor,
credential relay, watcher, daemon, or background dispatch process.
