#!/usr/bin/env python3
"""Multi-model extraction pass over un-extracted corpus rows.

Idempotent: skips rows that already have annotations.extractions, so it's safe to re-run as Leo
adds more receipts — only the new/un-extracted ones get processed. Leo-authorized cloud
(Azure prebuilt + Claude) + local qwen. Reuses handler.handle_analyze, so each row also fires
the P8.5 ocr.scan/ocr.divergence telemetry into the LAN-local events log.

    python3 run_extract_pass.py [provider,provider,...]   # default azure,claude,qwen
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from receipts import handler  # noqa: E402


def load_targets() -> list[str]:
    rows = [json.loads(line) for line in open(handler.DEFAULT_CORPUS_PATH, encoding="utf-8") if line.strip()]
    return [
        r["id"] for r in rows
        if r.get("image_path") and not (r.get("annotations", {}) or {}).get("extractions")
    ]


def main() -> int:
    providers = sys.argv[1].split(",") if len(sys.argv) > 1 else ["azure", "claude", "qwen"]
    ids = load_targets()
    print(f"[extract-pass] {len(ids)} rows to extract with {providers}", flush=True)
    ok = err = 0
    t0 = time.time()
    for i, rid in enumerate(ids, 1):
        ts = time.time()
        try:
            status, body = handler.handle_analyze(rid, {"providers": providers})
            if status == 200:
                ok += 1
                ex = body.get("extractions", {}) or {}
                good = [p for p, v in ex.items() if not (v or {}).get("error")]
                bad = [p for p, v in ex.items() if (v or {}).get("error")]
                print(f"[{i}/{len(ids)}] {rid} OK {int(time.time()-ts)}s ok={good} err={bad}", flush=True)
            else:
                err += 1
                print(f"[{i}/{len(ids)}] {rid} HTTP{status} {body.get('error')}", flush=True)
        except Exception as e:  # noqa: BLE001 — one row must not sink the batch
            err += 1
            print(f"[{i}/{len(ids)}] {rid} EXC {type(e).__name__}: {e}", flush=True)
    print(f"[extract-pass] DONE: {ok} ok, {err} err, {int(time.time()-t0)}s total", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
