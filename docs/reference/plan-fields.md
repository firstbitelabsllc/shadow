# PLAN.md fields

`PLAN.md` is the only work authority. The browser reads these Brief
fields:

- Outcome ID, Revision, Updated At, State, Outcome, Next
- Decision ID and Decision when state is `needs_input`
- Option A/B/C ID, label, and consequence
- Proof ID, relative Proof locator, Proof Summary, and Proof Delivery

Tasks use `pending`, `in_progress`, `blocked`, or `completed`. A blocked row
names a concrete resume condition. Large proof belongs in repository files;
the plan links to it.
