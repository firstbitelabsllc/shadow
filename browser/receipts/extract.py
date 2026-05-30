"""Multi-provider receipt extraction — flagship LLM vs prebuilt OCR, same contract.

Every provider emits the SAME `ScannedReceipt`-shaped object (see receipts.contract), so
prebuilt Azure Document Intelligence can be diffed field-for-field against a flagship
general-reasoning LLM. Providers:

- `azure`  — Azure DI `prebuilt-receipt` (receipts.ocr) mapped to ScannedReceipt.
- `claude` — Claude vision via the `claude` CLI (OAuth subscription; no API key needed),
             restricted to the Read tool.
- `codex`  — Codex vision via `codex exec` (run from a trusted git repo cwd).

Stdlib only. Provenance is injected in code (latency, provider name) — the LLM only extracts
the content fields. Each extractor returns:
    {"provider": str, "latency_ms": int, "expected": <ScannedReceipt|None>, "problems": [...], "error": str|None, "raw": str}
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from receipts import contract, ocr, storage

EXTRACT_PROMPT = (
    "You are a precise receipt-extraction engine. Read the receipt image at {path} and output "
    "ONLY a single JSON object (no prose, no markdown fences) with EXACTLY these keys:\n"
    '{{"merchantName": string|null, "merchantAddress": string|null, "transactionDate": string|null, '
    '"currencyCode": string|null, "currencySymbol": string|null, '
    '"lineItems": [{{"name": string, "amount": number|null, "quantity": number|null}}], '
    '"subtotal": number|null, "total": number|null, '
    '"extras": [{{"label": string, "amount": number, "kind": one of '
    '["tax","tip","fee","serviceCharge","mandate","surcharge","discount","credit","unknown"]}}]}}\n'
    "Rules: all amounts are JSON numbers. Comma-decimal like \"12,50\" -> 12.50. Strip thousands "
    "separators (\"1.234,50\"->1234.50, \"4,500\"->4500). No-decimal currencies (JPY/KRW) stay integers. "
    "currencyCode is ISO-4217 (EUR/USD/JPY/...). Put every tax/tip/service-charge/mandate/discount line "
    "into extras with the correct kind (a included service charge is serviceCharge, not tip). Output JUST the JSON."
)

LLM_CONTENT_KEYS = {
    "merchantName", "merchantAddress", "transactionDate", "currencyCode",
    "currencySymbol", "lineItems", "subtotal", "total", "extras",
}


def _provenance(provider_name: str, version: str, latency_ms: int) -> dict[str, Any]:
    return {
        "providerName": provider_name,
        "providerVersion": version,
        "scannedAt": storage.iso_now(),
        "latencyMs": latency_ms,
        "retryCount": 0,
    }


def _finalize(provider: str, version: str, content: dict | None, latency_ms: int, raw: str, error: str | None) -> dict:
    """Attach provenance, validate against the ScannedReceipt contract, package the result."""
    expected = None
    problems: list[str] = []
    if content is not None:
        cleaned = {k: v for k, v in content.items() if k in LLM_CONTENT_KEYS}
        cleaned.setdefault("lineItems", [])
        cleaned.setdefault("extras", [])
        cleaned["provenance"] = _provenance(provider, version, latency_ms)
        problems = contract.validate_expected(cleaned)
        expected = cleaned
    return {
        "provider": provider, "latency_ms": latency_ms, "expected": expected,
        "problems": problems, "error": error, "raw": raw[:2000],
    }


def _json_from_text(text: str) -> dict | None:
    """Pull the first JSON object out of model text (handles ```json fences + surrounding prose)."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        start = text.find("{")
        if start == -1:
            return None
        depth = 0
        for i in range(start, len(text)):
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            if depth == 0:
                candidate = text[start : i + 1]
                break
    if candidate is None:
        return None
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------- Azure (prebuilt)

def _num(field: dict | None) -> float | None:
    if not isinstance(field, dict):
        return None
    if "valueCurrency" in field and isinstance(field["valueCurrency"], dict):
        return field["valueCurrency"].get("amount")
    for key in ("valueNumber", "valueInteger", "value"):
        if isinstance(field.get(key), (int, float)):
            return field[key]
    return None


def _str(field: dict | None) -> str | None:
    if not isinstance(field, dict):
        return None
    return field.get("valueString") or field.get("content")


def azure_to_scanned(analyze: dict, latency_ms: int) -> dict:
    """Map an Azure prebuilt-receipt analyzeResult into a ScannedReceipt-shaped object."""
    result = analyze.get("analyzeResult", analyze)
    docs = result.get("documents") or []
    fields = docs[0].get("fields", {}) if docs else {}

    line_items = []
    for item in (fields.get("Items", {}).get("valueArray") or []):
        f = item.get("valueObject", {})
        line_items.append({
            "name": _str(f.get("Description")) or "",
            "amount": _num(f.get("TotalPrice")),
            "quantity": _num(f.get("Quantity")),
        })

    extras = []
    if _num(fields.get("TotalTax")) is not None:
        extras.append({"label": "Tax", "amount": _num(fields.get("TotalTax")), "kind": "tax"})
    if _num(fields.get("Tip")) is not None:
        extras.append({"label": "Tip", "amount": _num(fields.get("Tip")), "kind": "tip"})

    total_field = fields.get("Total", {})
    currency = (total_field.get("valueCurrency") or {}).get("currencyCode") if isinstance(total_field, dict) else None

    return {
        "merchantName": _str(fields.get("MerchantName")),
        "merchantAddress": _str(fields.get("MerchantAddress")),
        "transactionDate": _str(fields.get("TransactionDate")),
        "currencyCode": currency,
        "currencySymbol": None,
        "lineItems": line_items,
        "subtotal": _num(fields.get("Subtotal")),
        "total": _num(fields.get("Total")),
        "extras": extras,
    }


def extract_azure(image_bytes: bytes) -> dict:
    ready, msg = ocr.config_ready()
    if not ready:
        return _finalize("azure", "prebuilt-receipt", None, 0, "", f"not configured: {msg}")
    t0 = time.monotonic()
    try:
        analyze = ocr.analyze_receipt(image_bytes)
    except (ocr.OCRConfigError, ocr.OCRRequestError, ocr.OCRPollTimeout) as exc:
        return _finalize("azure", "prebuilt-receipt", None, int((time.monotonic() - t0) * 1000), "", str(exc))
    latency = int((time.monotonic() - t0) * 1000)
    content = azure_to_scanned(analyze, latency)
    return _finalize("azure", "prebuilt-receipt/2024-11-30", content, latency, json.dumps(analyze)[:2000], None)


# ---------------------------------------------------------------- LLM CLIs

def _run_cli(argv: list[str], cwd: Path | None = None, timeout: int = 180, input_text: str | None = None) -> tuple[str, str | None]:
    try:
        proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout, input=input_text)
    except FileNotFoundError:
        return "", f"{argv[0]} CLI not found"
    except subprocess.TimeoutExpired:
        return "", f"{argv[0]} timed out after {timeout}s"
    if proc.returncode != 0:
        return proc.stdout, (proc.stderr or f"{argv[0]} exit {proc.returncode}")[:400]
    return proc.stdout, None


def _claude_result_text(stdout: str) -> str:
    """The `claude -p --output-format json` payload is an array of events; the result text is
    the `result` field of the type=='result' element (or the whole thing if shapes change)."""
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        return stdout
    events = parsed if isinstance(parsed, list) else [parsed]
    for ev in reversed(events):
        if isinstance(ev, dict) and ev.get("type") == "result":
            return ev.get("result") or ""
    return stdout


def extract_claude(image_path: Path, model: str = "opus") -> dict:
    prompt = EXTRACT_PROMPT.format(path=str(image_path))
    # Prompt goes via stdin: `--allowedTools` is variadic and would swallow a trailing
    # positional prompt, so keep argv flags-only and feed the prompt through stdin.
    argv = [
        "claude", "-p", "--model", model, "--output-format", "json",
        "--permission-mode", "bypassPermissions", "--allowedTools", "Read",
    ]
    t0 = time.monotonic()
    stdout, error = _run_cli(argv, input_text=prompt)
    latency = int((time.monotonic() - t0) * 1000)
    if error:
        return _finalize("claude", model, None, latency, stdout, error)
    text = _claude_result_text(stdout)
    content = _json_from_text(text)
    return _finalize("claude", model, content, latency, text, None if content else "no JSON in claude output")


def extract_codex(image_path: Path, cwd: Path | None = None) -> dict:
    prompt = EXTRACT_PROMPT.format(path="the attached receipt image")
    # `-i` is variadic and would swallow a trailing positional prompt, so attach only the
    # image via -i and feed the prompt through stdin (codex reads the prompt from stdin when
    # not given positionally). Read-only sandbox, trusted git repo cwd.
    argv = ["codex", "exec", "--sandbox", "read-only", "-i", str(image_path)]
    t0 = time.monotonic()
    stdout, error = _run_cli(argv, cwd=cwd or Path.home() / "Development" / "vidux", input_text=prompt, timeout=180)
    latency = int((time.monotonic() - t0) * 1000)
    if error:
        return _finalize("codex", "codex-cli", None, latency, stdout, error)
    content = _json_from_text(_last_json_block(stdout))
    return _finalize("codex", "codex-cli", content, latency, stdout, None if content else "no JSON in codex output")


def _last_json_block(text: str) -> str:
    """Codex exec prints agent reasoning then the final answer; return the tail so _json_from_text
    picks the final JSON rather than an intermediate one."""
    idx = text.rfind("{")
    return text[max(0, idx - 1):] if idx != -1 else text


PROVIDERS = {"azure": extract_azure, "claude": extract_claude, "codex": extract_codex}


def extract(provider: str, image_path: Path) -> dict:
    """Dispatch one provider. Azure reads bytes; the LLM CLIs read the path directly."""
    if provider == "azure":
        return extract_azure(image_path.read_bytes())
    if provider == "claude":
        return extract_claude(image_path)
    if provider == "codex":
        return extract_codex(image_path)
    raise ValueError(f"unknown provider: {provider}")
