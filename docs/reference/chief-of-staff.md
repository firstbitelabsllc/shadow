# Chief of Staff brief

Pilot Puppy's Chief of Staff is a concise report over the same provider-neutral
state used by Vidux and 90. It is not an agent, queue, router, background
watcher, or acceptance authority.

The pure projection lives in [`browser/chief_of_staff.py`](https://github.com/firstbitelabsllc/vidux/blob/main/browser/chief_of_staff.py)
and its closed output contract is [`schemas/chief-of-staff.v1.json`](../../schemas/chief-of-staff.v1.json).
The caller supplies one validated `vidux.outcome.v1` document and, when
available, a small redacted plan summary. The projection never reads a plan or
writes a receipt itself.

## The five questions

The returned `vidux.chief-of-staff.v1` object answers:

- `changed`: what changed or what move is current;
- `matters`: why the outcome matters;
- `blocker`: the blocker or uncertainty, when one exists;
- `action`: what Leo needs to decide or do, when needed; and
- `recommendation`: the next bounded recommendation.

It includes at most three typed `choices` and one bounded `proof` reference.
Implementation details, provider/model names, prompts, transcripts, secrets,
and machine paths are rejected or never copied. A desk view and 90 can render
this same object; neither creates another queue or memory store.

The projection is deliberately not a completion claim. The owning host still
validates the Outcome, records the receipt, and folds accepted proof into the
canonical plan.
