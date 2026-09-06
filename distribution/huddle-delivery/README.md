# Optional Plan-B Huddle delivery runtime

Closed, owner-local notification entries for the shipped confined runner
(`scripts/shadow_huddle_event.py`). Delivery accelerates notice; it never
owns coordination, never mutates the board, and its absence changes nothing
about ownership, bids, or settlement.

## Layout

```
~/.shadow/
  board.json                          the one board (never child-writable)
  contacts/                           0700, stored contacts: <nonce>.json, 0600
  runtime/huddle-delivery/            0700
    shadow-huddle-deliver-event.py    event entrypoint (read-only descriptor)
    shadow-contact-register.py        registration entrypoint (+ contacts dir writable)
    shadow-huddle-provider-capabilities.json   armed per use, 0600, <= 16 KiB
```

Install with `./install-runtime.sh` (honors `SHADOW_HOME`).

## Arming capabilities (per use, ten-minute TTL)

```json
{"schema": "shadow.huddle-provider-capabilities.v1",
 "generated_at": "<UTC now>", "expires_at": "<UTC now + <=10 min>",
 "entries": [{"provider": "codex", "capability": "codex.turn-notify.v1",
              "transport": "exec", "target": "/exact/path/to/native-binary"}]}
```

Only `exec` transport to a single owner-owned native Mach-O executable is
admitted; `network` and `local_ipc` are refused before launch, and Grok
endpoints have no admitted transport. Write the descriptor 0600 immediately
before use; the runner refuses an expired, future-dated, or oversized one.

## Registering a contact

Pipe the unstored request to the CLI:

```
shadow huddle contact-register --seat SEAT <<'JSON'
{"schema": "shadow.huddle-contact.v1", "instance_nonce": "<uuid4>",
 "provider": "cmux", "capability": "cmux.surface-send.v1",
 "endpoint": {"surface_uuid": "<uuid4>"},
 "claim_keys": [{"entity": "...", "row": "~xx00", "claim_revision": 3,
                 "owner": "SEAT"}]}
JSON
```

`claim_keys` bind delivery to the seat's current claims: a contact whose
claims are returned, superseded, or stale becomes unreachable without any
cleanup. The stored lease is at most ten minutes from registration; expired
contacts are skipped, never pruned, by the event path.

## Delivery events

Board mutations emit four closed events post-commit (`huddle_changed`,
`round_opened`, `resolution_available`, `remote_recovery_required`). The
runner selects contacts whose claim keys intersect the huddle's current
claims (plus a handoff successor), projects one bounded envelope per
recipient — event identity and that contact's own endpoint only, never
board paths, seats, claim payloads, or other contacts — and executes the
armed target once with the envelope on stdin.

Exit protocol with the target: `0` accepted, `1` refused, `2` unsupported,
`3` unhealthy; signals, timeouts, and spawn failures are unhealthy. The
child's receipts are ephemeral closed output (`adapter`, `huddle_id`,
`idempotency_key`, `contact_nonce`, `attempted_at`, `outcome`) and are never
board authority.
