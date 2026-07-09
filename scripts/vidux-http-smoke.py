#!/usr/bin/env python3
"""Observe-only HTTP smoke helper for local monitor budgets."""

from __future__ import annotations

import argparse
import http.client
import json
import socket
import ssl
import sys
import time
from urllib.parse import urlparse


def _target(parsed):
    path = parsed.path or "/"
    if parsed.query:
        path += f"?{parsed.query}"
    return path


def _decode_sample(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def smoke_url(url: str, *, timeout: float = 3.0, max_sample_bytes: int = 512) -> dict:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return {
            "url": url,
            "verdict": "fail_url",
            "ok": False,
            "status": None,
            "duration_ms": 0,
            "bytes_read": 0,
            "timed_out": False,
            "partial": False,
            "error": "expected http:// or https:// URL",
            "sample": "",
        }

    started = time.monotonic()
    deadline = started + timeout
    bytes_read = 0
    sample = bytearray()
    status = None
    reason = ""
    timed_out = False
    error = ""
    conn: http.client.HTTPConnection | http.client.HTTPSConnection | None = None

    def remaining_timeout() -> float:
        return max(deadline - time.monotonic(), 0.001)

    try:
        port = parsed.port
        if parsed.scheme == "https":
            context = ssl.create_default_context()
            conn = http.client.HTTPSConnection(parsed.hostname, port, timeout=timeout, context=context)
        else:
            conn = http.client.HTTPConnection(parsed.hostname, port, timeout=timeout)
        conn.request("GET", _target(parsed), headers={"User-Agent": "vidux-http-smoke/1"})
        if conn.sock:
            conn.sock.settimeout(remaining_timeout())
        response = conn.getresponse()
        status = response.status
        reason = response.reason
        while True:
            if time.monotonic() >= deadline:
                timed_out = True
                error = f"timed out after {timeout:g}s"
                break
            if conn.sock:
                conn.sock.settimeout(remaining_timeout())
            try:
                chunk = response.read(4096)
            except (TimeoutError, socket.timeout):
                timed_out = True
                error = f"timed out after {timeout:g}s"
                break
            if not chunk:
                break
            bytes_read += len(chunk)
            if len(sample) < max_sample_bytes:
                sample.extend(chunk[: max_sample_bytes - len(sample)])
    except (TimeoutError, socket.timeout):
        timed_out = True
        error = f"timed out after {timeout:g}s"
    except (OSError, http.client.HTTPException) as exc:
        error = str(exc)
    finally:
        if conn is not None:
            conn.close()

    duration_ms = int((time.monotonic() - started) * 1000)
    partial = bool(timed_out and bytes_read)
    if timed_out:
        verdict = "warn_partial" if partial else "fail_budget"
    elif error:
        verdict = "fail_transport"
    elif status is not None and 200 <= status < 400:
        verdict = "pass"
    else:
        verdict = "fail_http"

    return {
        "url": url,
        "verdict": verdict,
        "ok": verdict == "pass",
        "status": status,
        "reason": reason,
        "duration_ms": duration_ms,
        "bytes_read": bytes_read,
        "timed_out": timed_out,
        "partial": partial,
        "error": error,
        "sample": _decode_sample(bytes(sample)),
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("urls", nargs="*", help="URL(s) to smoke with GET.")
    parser.add_argument("--url", action="append", default=[], help="URL to smoke. Repeatable.")
    parser.add_argument("--timeout", type=float, default=3.0, help="Total budget per URL in seconds.")
    parser.add_argument("--max-sample-bytes", type=int, default=512, help="Maximum response sample bytes to keep.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout must be greater than 0")
    if args.max_sample_bytes < 0:
        parser.error("--max-sample-bytes must be 0 or greater")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    urls = [*args.urls, *args.url]
    if not urls:
        sys.stderr.write("vidux-http-smoke: at least one URL is required\n")
        return 2

    results = [
        smoke_url(url, timeout=args.timeout, max_sample_bytes=args.max_sample_bytes)
        for url in urls
    ]
    warn_count = sum(1 for item in results if item["verdict"].startswith("warn"))
    fail_count = sum(1 for item in results if item["verdict"].startswith("fail"))
    exit_code = 1 if fail_count else 0
    payload = {
        "ok": fail_count == 0,
        "strict_ok": warn_count == 0 and fail_count == 0,
        "warning_only": warn_count > 0 and fail_count == 0,
        "warn_count": warn_count,
        "fail_count": fail_count,
        "exit_code": exit_code,
        "results": results,
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for item in results:
            print(
                f"{item['verdict']} status={item['status']} "
                f"duration_ms={item['duration_ms']} bytes={item['bytes_read']} {item['url']}"
            )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
