# F3 public semantic-boundary note

This file is retained as a public-safe contract note. It is not a private
execution receipt and contains no external repository locator, source
revision, provider, credential, machine path, transcript, or raw payload.
External on-the-go consumer validation is intentionally outside this public
repository and is not claimed here.

## Public proof surface

The maintained Vidux tree defines and tests the revision-bound
`vidux.drive.v1` projection and its compare-and-set choice receipt:

- `browser/drive_mode.py` keeps the projection bounded and provider-neutral.
- `tests/test_drive_mode.py` covers current, stale, hidden-option, and
  non-executing choice results.
- `tests/test_outcome_source.py` checks that the canonical Outcome revision and
  identity are preserved when the browser prepares its projections.

These checks prove the public semantic boundary only. They do not prove that
an external consumer ran, selected a provider, executed coding work, or
transported credentials. Such a consumer may validate this contract in its
own private authority without adding its receipt to the public source.
