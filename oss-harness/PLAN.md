# Open-source release plan

This public plan covers only Vidux itself. It deliberately excludes private
account configuration, non-public repositories, worker execution logs,
personal paths, billing data, session data, and unpublished portfolio
decisions.

## Outcome

Keep Vidux a small, local-first plan/proof/resume layer that complements coding
agents instead of competing with their execution engines.

## Constraints

- Public examples use synthetic identities and repository-neutral paths.
- Release claims require exact-tag tests, package verification, and a current
  public-boundary scan.
- Provider routing, authentication, billing, and private fleet operations stay
  outside this repository.
- No release may claim execution, scheduling, proof authentication, or remote
  worker control that Vidux does not provide.

## Tasks

- [completed] Publish the provider-neutral Outcome / Ask / Steer contract.
- [completed] Require test, package, secret-scan, and public-boundary gates.
- [completed] Sanitize the maintained public tip and source package while
  retaining the repository's existing ancestry under the no-rewrite policy.
- [pending] Evaluate future changes against stranger usability and the narrow
  plan/proof/resume contract before expanding the product.

## Proof

- `npm run verify`
- `npm run release:verify`
- `npm run test:e2e`
- hosted CI, CodeQL, secret scanning, and dependency alerts

The maintained tip and source package are the supported public surfaces.
Existing ancestry remains unchanged, so this plan does not claim historical
erasure. Detailed portfolio operations belong in their own non-public
authority and must not be appended here.
