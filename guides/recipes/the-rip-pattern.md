# Recipe: Simplify an overbuilt surface

Use this when product evidence shows that a default interface exposes more
controls than its users or data require.

## Steps

1. Record the observed product problem and desired outcome in `PLAN.md`.
2. Name the specific default-surface elements that should disappear.
3. Preserve data and service behavior unless evidence says they are wrong.
4. Reduce the default surface to the smallest obvious task.
5. Add a regression gate for the intended shape.
6. Verify the real user path with representative empty and populated states.
7. Record proof, remaining risk, and one resume action; then stop.

Do not move controls to hidden routes merely to preserve implementation work.
Keep a secondary surface only when a real user outcome needs it.

## Gate

- The default task is materially easier to understand.
- Existing data remains readable.
- Removed behavior is not still advertised in docs or navigation.
- Screenshots or interaction proof cover the states that motivated the change.
