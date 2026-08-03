# Outcome contract

`pilot-puppy.outcome.v1` contains one Outcome, optional A/B/C question, bounded
decision receipts, and relative proof references. The deterministic validator is:

```bash
python3 scripts/pilot-puppy-outcome-validate.py \
  --input examples/outcome-choice/example.json
```

It exits `0` for valid, `1` for invalid, and `2` for invocation or I/O failure.
The schema intentionally excludes provider, model, prompt, transcript,
credential, command, session, and absolute-path fields.
