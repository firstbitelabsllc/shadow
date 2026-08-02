# F0.5 private Chief-of-Staff receipt

This is a sanitized semantic receipt for the private 90 Chief-of-Staff client.
It contains no transcript, screen, command path, provider, credential, or raw
source content.

## Source references

| Surface | Exact reference |
| --- | --- |
| Public Vidux projection | `firstbitelabsllc/vidux` `e4e60968afad2dad0e0bfd0b0a5b481eb0d6a87` |
| Private 90 implementation | ai-leo PR #209; source `7d63c775fdd277962e7c12e8b0f94220a567efa4`; private main `5f58daae358ab8b3b132ef2eb13b15c69082dfad` |
| Private focused unit gate | `test_chief_client.py`: 6/6 |
| Public focused projection gate | `test_chief_of_staff` + `test_drive_mode`: 16/16 |

## One same-source run

One validated `vidux.outcome.v1` document at revision `4` was projected by the
public Chief-of-Staff adapter and consumed by the private 90 adapter. Both
retained Outcome `publish-notes`; 90 exposed exactly `A/B/C`, omitted the proof
locator and private/provider fields, and reproduced the public plain-speech
string. The source document was unchanged.

The combined private record, Drive, and Chief client gate was 17/17 and the
private record validator returned `0`. This proves semantic presentation from
one source revision only; it does not prove execution, routing, or provider
selection.
