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

`pilot-puppy roster` is separate local setup data. It is not a project
authority or receipt, and `browse` and `status` never read it. Keep named-seat
details private; Pilot Puppy does not store provider, model, account, or quota
data in browser output, status output, or receipts.

`pilot-puppy route` may write a small project evidence packet, but that packet
contains only generic roles, native-host surfaces, bounded state, and hashes.
It excludes roster slot IDs, task text, local paths, model/account/quota data,
commands, credentials, provider payloads, and transcripts.
