# Harness authoring

A useful agent prompt stays short because repository state belongs in
`PLAN.md`, not in a recurring instruction blob.

Include only:

1. the outcome and owning plan path;
2. the worker's bounded read/write surface;
3. the verification gate;
4. hard safety boundaries;
5. the required proof and cold-resume handoff.

Do not embed task numbers, branch state, account information, runtime
identifiers, provider receipts, or raw conversations. A new run should discover
current state from the repository rather than trusting a copied session.

Worker output is a draft until the owning agent reviews the diff and reproduces
the important proof.
