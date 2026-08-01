# Local telemetry contract

Pilot Puppy telemetry is an optional, bounded quality signal. It is not a
planner, queue, provider router, transcript archive, or completion authority.

The public seed lives in [`browser/telemetry.py`](https://github.com/firstbitelabsllc/vidux/blob/main/browser/telemetry.py).
`build_event()` accepts only semantic lifecycle facts such as an outcome id,
plan revision, native host, state, proof status, retry counts, and elapsed-time
metadata. Prompts, transcripts, file contents, credentials, personal paths,
and arbitrary attributes are rejected.

`to_otlp()` wraps that allowlisted event in a small OTLP/HTTP JSON trace
envelope. `emit_local()` is disabled unless the caller explicitly supplies
`VIDUX_TELEMETRY_ENDPOINT` or an endpoint argument, and it accepts only a
loopback URL. No authorization header or remote fallback is added.

This is a contract and redaction seed for flagship F5. It does not claim that a
collector, Langfuse sink, or production exporter has been installed. F5 stays
open until a real local collector receives completion and failure spans and
the hosted privacy gate covers the full integration.
