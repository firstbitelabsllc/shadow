# Recipe: Host prompt mirror

Use this only when a coding host reads a machine-local prompt that contains a
durable repository constraint.

## Contract

1. Put the durable constraint in `PLAN.md` or a linked repository document.
2. Configure the coding host to reference that file using its supported setup.
3. Keep transient task instructions in the host; do not copy sessions,
   credentials, provider receipts, or account state into the repository.
4. When the constraint changes, update the repository authority first and
   verify the host still reads the intended revision.

Choose a repository path appropriate to the project, such as
`docs/<host-prompt>.md`. Vidux does not create, synchronize, or repair the
host's prompt store.

## Gate

- The repository constraint is reviewable without access to one machine.
- The host configuration points to the documented file.
- Removing the host integration leaves `PLAN.md` and Git sufficient to resume.
