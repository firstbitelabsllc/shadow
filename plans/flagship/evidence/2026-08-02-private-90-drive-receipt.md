# F3 private 90 Drive receipt

This is the sanitized semantic receipt for the private 90 consumer that closes
the public F3 owner handoff. It contains no transcript, screen, command path,
provider, credential, or source content.

## Source references

| Surface | Exact reference |
| --- | --- |
| Public Vidux host and validator | `firstbitelabsllc/vidux` `6f3d64f84b53a60b2d093ea267e1e89aaba9568e` |
| Private 90 implementation | ai-leo PR #206; source `d46602c078429c9001c7916103e02bbdd1dbda46`; private main `15f663fb254345d6c88cf90175e4485a8d4f8d49` |
| Private authority receipt | ai-leo PR #207; private main `76a40cdf31664252dd04c7a333eeb393ee330880` |
| Private unit gate | `test_check_record.py` + `test_drive_client.py`: 11/11 |

## One sanitized run

The run began with one canonical-validator-green `vidux.outcome.v1` document at
revision `4`. The public `project_drive` projection and the public
`vidux.chief-of-staff.v1` brief identified the same Outcome. The private 90
client presented the first three choices and emitted exactly:

```json
{
  "schema": "vidux.drive-steer.v1",
  "kind": "answer",
  "revision": 4,
  "outcome_id": "publish-notes",
  "ask_id": "choose-release",
  "option_id": "hold-review"
}
```

The owning public `receive_choice` helper returned these bounded results:

| Input | Receipt | Next revision | Canonical validator |
| --- | --- | ---: | ---: |
| current revision `4` | `received` / `accepted` | `5` | `0` |
| stale choice against authority revision `5` | `superseded` / `stale_revision` | `6` | `0` |
| hidden option `write-note` | `not_delivered` / `option_not_visible` | `5` | `0` |

The original Outcome was not mutated. No provider, execution, storage, shell,
network, queue, credential, or raw-content field crossed the boundary. The
receipt proves semantic handoff only; it does not claim that coding work ran.
