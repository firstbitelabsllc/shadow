# F0.5 public Chief-of-Staff semantic-boundary note

This file is retained as a public-safe contract note. It is not a private
execution receipt and contains no external repository locator, source
revision, provider, credential, machine path, transcript, or raw payload.
External on-the-go consumer validation is intentionally outside this public
repository and is not claimed here.

## Public proof surface

The maintained Vidux tree defines and tests the typed
`vidux.chief-of-staff.v1` projection:

- `browser/chief_of_staff.py` accepts only bounded semantic fields and rejects
  implementation or private detail.
- `browser/static/chief-of-staff.js` renders the same provider-neutral brief,
  caps choices, and fails closed on unsafe input.
- `tests/test_chief_of_staff.py` and
  `browser/tests/unit/chief-of-staff.test.mjs` cover projection, rendering,
  escaping, and privacy rejection.

These checks prove the public semantic presentation boundary only. They do
not prove that an external consumer ran, selected a provider, executed coding
work, or transported credentials. An external consumer may validate this
contract in its own authority without adding a receipt to the public source.
