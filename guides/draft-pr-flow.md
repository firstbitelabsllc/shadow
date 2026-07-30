# Draft pull-request flow

Use the repository host's normal pull-request tooling. Vidux supplies no PR
publisher.

1. Read the owning plan and inspect existing branches and pull requests.
2. Make one bounded change on a clearly owned branch or worktree.
3. Run the repository's real verification gate.
4. Open a draft pull request with:
   - the outcome;
   - changed paths;
   - proof reproduced at the exact revision;
   - risks or unresolved findings;
   - rollback and cold-resume instructions.
5. Update the owning plan with the pull-request link and proof.

Do not call a pull request shipped merely because it exists. Merge, deployment,
and user-visible delivery are separate receipts.
