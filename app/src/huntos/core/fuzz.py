"""The doctrine battery, automated - the Fuzz-Engineer's repetitive work.

NOT a smart fuzzer: `probe` fires HUNT-OS's standard edge-case battery (one
ordinary-value baseline, then the BATTERY entries) at a single endpoint
parameter and records how the server answered. The value is in the OBSERVER
data on every probe - status, elapsed_ms, body_len, body_hash - and in the
`anomalies` helper that separates "the server shrugged" from "the server
flinched".

Honest boundary: a flinch is a LEAD, not a finding. The heuristics here
(status drift, unique error-class bodies, 4x timing) are triage for
human/engine judgment; the lead mutation loop and the oracle still have to
prove anything the battery surfaces. The CLI records every probe as a
fuzz_probe event through the normal log path (redaction applies) and leaves
lead creation manual on purpose.

Stdlib only (urllib). A probe never raises: network failures come back as
status=0 rows carrying an error string, so one dead endpoint aborts nothing.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request

# The doctrine's standard edge-case battery, as (name, payload) pairs. String
# payloads ride as the value of the fuzzed parameter (query var for GET,
# form-encoded body for POST); dict payloads ride as a JSON body
# (Content-Type: application/json).
BATTERY = [
    ("empty", ""),
    ("zero", "0"),
    ("negative", "-1"),
    ("max_uint", str(2**256 - 1)),
    ("huge_string", "A" * 4096),
    ("null_bytes", "AB\x00CD"),
    ("unicode", "\u200b\u00a0\U0001F600"),
    ("type_juggle", {"bypass": True}),
    ("sqlish", "' OR 1=1 --"),
    ("format", "%s%s%n"),
]

# The ordinary-value probe fired FIRST: the yardstick every battery entry is
# measured against by `anomalies`.
BASELINE = ("baseline", "1")

# The query var / form field used when the caller does not name a param.
DEFAULT_PARAM = "q"

# payload_preview is a truncated look at the payload, never the payload itself
# (a 4 KiB string has no business in a table row or an event detail).
PREVIEW_LIMIT = 40


def _preview(payload) -> str:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return text[:PREVIEW_LIMIT]


def _fire(url: str, method: str, body, headers: dict, timeout: float):
    """One HTTP round trip. Returns (status, body_bytes, error_or_None).

    An HTTP error response (4xx/5xx) is a RESPONSE, not a failure - HTTPError
    carries the status and the body, so a 500 is data exactly like a 200. Only
    the network layer (refused, DNS, timeout, reset) yields status=0 + error.
    Never raises: the battery must survive one dead endpoint.
    """
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(getattr(resp, "status", 0) or resp.code), resp.read(), None
    except urllib.error.HTTPError as e:
        try:
            raw = e.read()
        except Exception:  # noqa: BLE001 - even reading the error body must not raise
            raw = b""
        return int(e.code), raw, None
    except Exception as e:  # noqa: BLE001 - a probe never raises (module contract)
        msg = str(e).strip()
        return 0, b"", (f"{type(e).__name__}: {msg}" if msg else type(e).__name__)


def probe(url: str, method: str = "GET", param: str | None = None,
          payloads: list | None = None, timeout: float = 10.0,
          headers: dict | None = None) -> list[dict]:
    """Fire the battery at one parameter. Returns one dict per probe, the
    baseline first: {payload_name, payload_preview, status, elapsed_ms,
    body_len, body_hash, error} - error is "" on any answered probe and the
    failure message on status=0 rows (network layer only).

    String payloads become the value of `param` (query var for GET,
    form-encoded body for POST with Content-Type:
    application/x-www-form-urlencoded; the var is DEFAULT_PARAM when param is
    None). Dict payloads become a JSON body (Content-Type: application/json)
    regardless of method. body_hash is sha256[:16] of the response body (''
    when the request never got a response). Caller `headers` ride on every
    probe; Content-Type is set from the payload encoding, so it wins over a
    caller-supplied value.
    """
    method = (method or "GET").upper()
    name = param if param else DEFAULT_PARAM
    battery = BATTERY if payloads is None else list(payloads)
    base_headers = dict(headers or {})
    results = []
    for entry in [BASELINE, *battery]:
        if isinstance(entry, (tuple, list)) and len(entry) == 2:
            payload_name, payload = entry
        else:  # a bare payload: name it by its (truncated) shape
            payload = entry
            payload_name = _preview(payload)
        if isinstance(payload, dict):
            body = json.dumps(payload).encode("utf-8")
            req_url = url
            req_headers = {**base_headers, "Content-Type": "application/json"}
        elif method == "GET":
            body = None
            sep = "&" if "?" in url else "?"
            req_url = f"{url}{sep}{urllib.parse.urlencode({name: payload})}"
            req_headers = base_headers
        else:
            body = urllib.parse.urlencode({name: payload}).encode("utf-8")
            req_url = url
            req_headers = {
                **base_headers,
                "Content-Type": "application/x-www-form-urlencoded",
            }
        started = time.perf_counter()
        status, raw, error = _fire(req_url, method, body, req_headers, timeout)
        elapsed_ms = int(round((time.perf_counter() - started) * 1000))
        row = {
            "payload_name": payload_name,
            "payload_preview": _preview(payload),
            "status": status,
            "elapsed_ms": elapsed_ms,
            "body_len": len(raw),
            "body_hash": hashlib.sha256(raw).hexdigest()[:16] if status else "",
            "error": error or "",
        }
        results.append(row)
    return results


def anomalies(results: list[dict]) -> list[dict]:
    """The anomalous subset of a probe() run, in run order. A probe flinches
    when:

      - its status differs from the baseline's (the server changed its mind),
      - OR its body is UNIQUE among identical-status probes AND the status is
        an error class (>=400) - a distinctive error body smells like a stack
        trace or a debug dump,
      - OR it took more than 4x the baseline's time (timing side channel).
        Only answered probes are compared: a failed connection's latency is
        noise, not a signal.

    The baseline itself is never flagged. Heuristics, not findings: every
    match here is a lead candidate for human/engine judgment.
    """
    baseline = next((r for r in results if r.get("payload_name") == BASELINE[0]), None)
    if baseline is None:
        return []
    base_status = baseline["status"]
    base_ms = baseline["elapsed_ms"]
    seen = {}
    for r in results:
        key = (r.get("status"), r.get("body_hash") or "")
        seen[key] = seen.get(key, 0) + 1
    flagged = []
    for r in results:
        if r is baseline:
            continue
        status = r.get("status")
        if status != base_status:
            flagged.append(r)
            continue
        if status and status >= 400 and r.get("body_hash") and seen[(status, r["body_hash"])] == 1:
            flagged.append(r)
            continue
        if status and base_status and base_ms > 0 and r.get("elapsed_ms", 0) > 4 * base_ms:
            flagged.append(r)
    return flagged
