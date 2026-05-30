"""Multi-provider receipt extraction — flagship LLM vs prebuilt OCR, same contract.

Every provider emits the SAME `ScannedReceipt`-shaped object (see receipts.contract), so
prebuilt Azure Document Intelligence can be diffed field-for-field against a flagship
general-reasoning LLM. Providers:

- `azure`  — Azure DI `prebuilt-receipt` (receipts.ocr) mapped to ScannedReceipt (full-res).
- `claude` — Claude vision via the `claude` CLI (OAuth, no API key). Default model `sonnet`
             (accurate; opus timed out on a 12MP photo). Image is resized before the call.
- `qwen`   — qwen2.5-VL:7b via local ollama (free + private; ~matches the cloud flagship and,
             like claude, catches surcharge/fee lines Azure's [tax,tip] schema drops).
- `gemma3` — gemma3:12b via local ollama. KEEP for benchmarking only — it hallucinated
             merchant + line items on a real receipt; do NOT trust for production.
- `codex`  — Codex vision via `codex exec` (correct invocation; OpenAI account quota-gated).

Benchmark finding (2026-05-30 Marathon Cafe receipt): both claude-sonnet and qwen2.5-VL recovered
a 3% credit-card processing fee that Azure prebuilt dropped — the aggregate signal P7 feeds back
into Resplit's reconciliation (Azure under-extracts non-tax/tip extras).

LLM providers resize the image to <=1568px first (a 12MP photo makes them crawl / time out).
Provenance is injected in code; the LLM only extracts the content fields. Each extractor returns:
    {"provider": str, "latency_ms": int, "expected": <ScannedReceipt|None>, "problems": [...], "error": str|None, "raw": str}
"""

from __future__ import annotations

import io
import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from receipts import contract, ocr, storage

VISION_MAX_DIM = 1568  # Claude's optimal long-edge; also right-sizes local vision models.
OLLAMA_URL = "http://localhost:11434/api/generate"


def _resize_for_vision(image_bytes: bytes, max_dim: int = VISION_MAX_DIM, quality: int = 88) -> bytes:
    """Downscale a large receipt photo for LLM vision. Returns the original bytes if PIL is
    unavailable or the image already fits. (Azure prebuilt gets the full-res image, not this.)"""
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return image_bytes
    try:
        im = Image.open(io.BytesIO(image_bytes))
    except Exception:
        return image_bytes
    # Bake in EXIF orientation BEFORE measuring/resizing — phone photos carry a rotation tag that
    # Azure prebuilt honors server-side but the vision LLMs (claude/qwen) do NOT. Without this the
    # models see sideways receipts and the whole prebuilt-vs-flagship benchmark is skewed.
    try:
        orientation = im.getexif().get(0x0112)  # 274 = Orientation; 1/None = upright
    except Exception:
        orientation = None
    needs_rotate = orientation not in (None, 1)
    im = ImageOps.exif_transpose(im).convert("RGB")
    w, h = im.size
    if max(w, h) <= max_dim and not needs_rotate:
        return image_bytes  # already upright and within budget — return the original bytes
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        im = im.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
    out = io.BytesIO()
    im.save(out, "JPEG", quality=quality)
    return out.getvalue()

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
        amt = field["valueCurrency"].get("amount")
        # Guard like the other branches — a non-numeric (or bool) amount must not leak through.
        return amt if isinstance(amt, (int, float)) and not isinstance(amt, bool) else None
    for key in ("valueNumber", "valueInteger", "value"):
        val = field.get(key)
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return val
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
    # P8.4 free win: TaxDetails[] is a per-tax breakdown Azure already returns (state + city +
    # service tax as distinct lines). Prefer it over the collapsed TotalTax so multi-tax receipts
    # don't lose a tax line. Falls back to TotalTax when TaxDetails is absent.
    tax_details = (fields.get("TaxDetails", {}) or {}).get("valueArray") or []
    emitted_tax = False
    for td in tax_details:
        f = td.get("valueObject", {})
        amt = _num(f.get("Amount"))
        if amt is not None:
            extras.append({"label": _str(f.get("Description")) or "Tax", "amount": amt, "kind": "tax"})
            emitted_tax = True
    if not emitted_tax and _num(fields.get("TotalTax")) is not None:
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


def extract_claude(image_path: Path, model: str = "sonnet") -> dict:
    """`claude -p` is an AGENT, not a raw vision call — it sees the image only after invoking the
    Read tool, so the prompt points at a (resized) file path and we allow only the Read tool.
    Default `sonnet`: accurate at ~50s; `opus` timed out on a 12MP photo; `haiku` is ~2x faster
    but hallucinated line items on a real receipt. Prompt via stdin (--allowedTools is variadic)."""
    import tempfile

    resized = _resize_for_vision(image_path.read_bytes())
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
        tf.write(resized)
        tmp = Path(tf.name)
    try:
        prompt = EXTRACT_PROMPT.format(path=str(tmp))
        argv = [
            "claude", "-p", "--model", model, "--output-format", "json",
            "--permission-mode", "bypassPermissions", "--allowedTools", "Read",
        ]
        t0 = time.monotonic()
        stdout, error = _run_cli(argv, input_text=prompt, timeout=150)
        latency = int((time.monotonic() - t0) * 1000)
    finally:
        tmp.unlink(missing_ok=True)
    if error:
        return _finalize("claude", model, None, latency, stdout, error)
    text = _claude_result_text(stdout)  # event array -> the .result string (often ```json fenced)
    content = _json_from_text(text)
    return _finalize("claude", model, content, latency, text, None if content else "no JSON in claude output")


def extract_ollama_vision(image_path: Path, model: str, *, label: str) -> dict:
    """Local vision via ollama /api/generate with format=json. Free + private. The resized image
    is base64-attached. qwen2.5-VL matches the cloud flagship; gemma3 hallucinates (benchmark-only)."""
    import base64

    resized = _resize_for_vision(image_path.read_bytes())
    body = json.dumps({
        "model": model,
        "prompt": EXTRACT_PROMPT.format(path="the attached image"),
        "images": [base64.b64encode(resized).decode("ascii")],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
    }).encode()
    request = urllib.request.Request(OLLAMA_URL, data=body, headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        return _finalize(label, model, None, int((time.monotonic() - t0) * 1000), "", f"ollama unreachable/error: {exc}")
    latency = int((time.monotonic() - t0) * 1000)
    raw = payload.get("response", "")
    content = _json_from_text(raw)
    return _finalize(label, model, content, latency, raw, None if content else "no JSON in ollama response")


def extract_qwen(image_path: Path) -> dict:
    return extract_ollama_vision(image_path, "qwen2.5vl:7b", label="qwen")


def extract_gemma3(image_path: Path) -> dict:
    return extract_ollama_vision(image_path, "gemma3:12b", label="gemma3")


# JSON Schema for codex `--output-schema` (structured output) — the LLM content fields
# (provenance is injected in code, not extracted). Strict shape: all keys required,
# additionalProperties false, extras.kind constrained to the 9 ScannedExtraKind rawValues.
CODEX_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["merchantName", "merchantAddress", "transactionDate", "currencyCode",
                 "currencySymbol", "lineItems", "subtotal", "total", "extras"],
    "properties": {
        "merchantName": {"type": ["string", "null"]},
        "merchantAddress": {"type": ["string", "null"]},
        "transactionDate": {"type": ["string", "null"]},
        "currencyCode": {"type": ["string", "null"]},
        "currencySymbol": {"type": ["string", "null"]},
        "subtotal": {"type": ["number", "null"]},
        "total": {"type": ["number", "null"]},
        "lineItems": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["name", "amount", "quantity"],
            "properties": {"name": {"type": "string"}, "amount": {"type": ["number", "null"]},
                           "quantity": {"type": ["number", "null"]}}}},
        "extras": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["label", "amount", "kind"],
            "properties": {"label": {"type": "string"}, "amount": {"type": "number"},
                           "kind": {"type": "string", "enum": sorted(contract.EXTRA_KINDS)}}}},
    },
}


def extract_codex(image_path: Path, cwd: Path | None = None) -> dict:
    import shutil
    import tempfile

    workspace = cwd or Path.home() / "Development" / "vidux"  # trusted git repo
    prompt = EXTRACT_PROMPT.format(path="the attached receipt image")
    t0 = time.monotonic()
    # Schema + answer files must live INSIDE the workspace so the workspace-write sandbox can
    # write the -o answer (a read-only sandbox can't write; /tmp is outside the writable root).
    tmp = Path(tempfile.mkdtemp(prefix=".codex-receipt-", dir=workspace))
    try:
        schema_file = tmp / "schema.json"
        out_file = tmp / "answer.json"
        schema_file.write_text(json.dumps(CODEX_SCHEMA), encoding="utf-8")
        # Image via -i; prompt via stdin; structured output via --output-schema; final answer
        # to -o (codex's human log goes to stderr, so stdout is unreliable).
        # --ignore-user-config drops the MCP-server reconnect spam from config.toml (sentry/figma/
        # cloudflare) that otherwise floods stderr; it doesn't affect the extraction. Resize the
        # image like the other LLM providers.
        resized = _resize_for_vision(image_path.read_bytes())
        img_file = tmp / "receipt.jpg"
        img_file.write_bytes(resized)
        argv = [
            "codex", "exec", "--ignore-user-config", "--sandbox", "workspace-write",
            "--output-schema", str(schema_file), "-o", str(out_file), "-i", str(img_file),
        ]
        stdout, error = _run_cli(argv, cwd=workspace, input_text=prompt, timeout=240)
        latency = int((time.monotonic() - t0) * 1000)
        answer = out_file.read_text(encoding="utf-8") if out_file.exists() else ""
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    content = _json_from_text(answer) if answer else None
    if content is None and error:
        return _finalize("codex", "gpt-5.5", None, latency, answer or stdout, error)
    return _finalize("codex", "gpt-5.5", content, latency, answer, None if content else "no JSON in codex answer file")


# provider name -> callable taking a Path. azure reads bytes; the rest take the image path.
PROVIDERS = {
    "azure": lambda p: extract_azure(p.read_bytes()),
    "claude": extract_claude,
    "qwen": extract_qwen,
    "gemma3": extract_gemma3,
    "codex": extract_codex,
}


def extract(provider: str, image_path: Path) -> dict:
    """Dispatch one provider by name."""
    fn = PROVIDERS.get(provider)
    if fn is None:
        raise ValueError(f"unknown provider: {provider} (known: {sorted(PROVIDERS)})")
    return fn(image_path)
