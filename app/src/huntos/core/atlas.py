"""Crypto-attack atlas: the vuln taxonomy the hunt skills route through.

The atlas is DATA, shipped with the package inside the skill corpus
(``_data/idea/skills/web3/crypto-attack-atlas/data/atlas.json``) so it travels
with `hunt install` and the plugin mirror without a second copy to drift. It
carries 18 attack families (A1..A18), each bound to:

  - the HUNT-OS klass it files under (label discipline: the ledger's taxonomy),
  - the SWC entries and the observable signals,
  - the concrete detection commands an operator can run,
  - the mitigations,
  - the existing skills that already cover part of the family,
  - incident counts and parsed-USD evidence from the 904-incident dataset.

This module only READS. It never opens the hunt db and never writes one: the
CLI is the sole write door, so `hunt atlas` may suggest `hunt lead add ...`
lines but never execute them.

Honest limits: the family counts are keyword-classified over root-cause prose,
and ``loss_usd_parsed`` is a lower bound (only incidents that state USD are
summed). Treat the atlas as "what to test next", not as an industry total.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

# Resolved from the package root: <package>/huntos/_data/idea/skills/web3/...
_DEFAULT_REL = os.path.join("_data", "idea", "skills", "web3",
                            "crypto-attack-atlas", "data", "atlas.json")
ATLAS_REL = _DEFAULT_REL

_cache: dict | None = None


def atlas_path() -> Path:
    """Path of the shipped atlas.json (overridable for tests)."""
    return Path(__file__).resolve().parents[1] / ATLAS_REL


def load() -> dict:
    """Load the atlas once per process. Raises ValueError when it is missing.

    A missing/corrupt atlas is a packaging fault, not an operator error, so the
    message says which path failed instead of leaking a JSONDecodeError.
    """
    global _cache
    if _cache is not None:
        return _cache
    path = atlas_path()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except OSError as exc:
        raise ValueError(f"BLOCKED: atlas data missing at {path} ({exc})") from None
    except json.JSONDecodeError as exc:
        raise ValueError(f"BLOCKED: atlas data corrupt at {path} ({exc})") from None
    if not isinstance(data, dict) or not data.get("families"):
        raise ValueError(f"BLOCKED: atlas data has no families ({path})")
    _cache = data
    return data


def families() -> list[dict]:
    return load()["families"]


def klasses() -> list[str]:
    """Distinct HUNT-OS klass values the atlas files under, in atlas order."""
    seen: list[str] = []
    for f in families():
        if f["klass"] not in seen:
            seen.append(f["klass"])
    return seen


def get(ref: str) -> dict | None:
    """Resolve a family by id (A7 / a7), key (reentrancy), or name (Reentrancy)."""
    if not ref:
        return None
    want = ref.strip().lower()
    for f in families():
        if want in (f["id"].lower(), f.get("family", "").lower(), f["name"].lower()):
            return f
    # tolerate a class-ish prefix, e.g. "A07"
    if want.startswith("a") and want[1:].isdigit():
        return get(f"A{int(want[1:])}")
    return None


def match(text: str, top: int = 3) -> list[tuple[dict, list[str]]]:
    """Rank families against a free-text symptom/description.

    Scoring is deterministic and explainable: one point per keyword hit, so the
    caller can see WHY a family was suggested instead of trusting a black box.
    An empty match returns nothing — the CLI then says so and points at
    `hunt atlas list` rather than inventing a family.
    """
    words = (text or "").lower()
    if not words.strip():
        return []
    scores: list[tuple[int, dict, list[str]]] = []
    for f in families():
        hits = [k for k in load().get("keywords", {}).get(f["id"], []) if k in words]
        if hits:
            scores.append((len(hits), f, hits))
    scores.sort(key=lambda t: (-t[0], t[1]["id"]))
    return [(f, hits) for _, f, hits in scores[:top]]


def by_klass(klass: str) -> list[dict]:
    want = (klass or "").strip().lower()
    return [f for f in families() if f["klass"].lower() == want]


def coverage(findings: list[dict], leads: list[dict] | None = None) -> dict:
    """Map recorded findings/leads onto atlas families.

    ``findings`` rows need a ``klass`` key (the db's column) — findings are the
    authoritative link because the ledger enforces that klass. ``leads`` carry
    no klass in the schema, so a lead is attributed to a family by keyword
    match on its title; that is an approximation by construction, which is why
    the caller prints leads separately from findings instead of summing them
    into one "coverage" number.

    Returns per-family rows plus the families with no evidence at all, so the
    caller can print blind spots rather than a percentage that hides them.
    """
    leads = leads or []
    have_finding: dict[str, int] = {}
    have_lead: dict[str, int] = {}
    for row in findings:
        for f in by_klass(row.get("klass") or ""):
            have_finding[f["id"]] = have_finding.get(f["id"], 0) + 1
    for row in leads:
        ranked = match(row.get("title") or "", top=1)
        if ranked:
            fam = ranked[0][0]
            have_lead[fam["id"]] = have_lead.get(fam["id"], 0) + 1
    rows = []
    for f in families():
        rows.append({
            "id": f["id"], "name": f["name"], "klass": f["klass"],
            "findings": have_finding.get(f["id"], 0),
            "leads": have_lead.get(f["id"], 0),
            "incidents_total": f.get("incidents_total", 0),
        })
    uncovered = [r for r in rows if not r["findings"] and not r["leads"]]
    covered = [r for r in rows if r["findings"] or r["leads"]]
    return {"rows": rows, "covered": covered, "uncovered": uncovered,
            "klasses": klasses()}


def seed_leads(family: dict) -> list[str]:
    """`hunt lead add` lines for a family — printed, never executed.

    One lead per family: the first signal becomes the bounded hypothesis title,
    so the operator/agent has a ledger-shaped next step instead of prose.
    """
    signal = (family.get("signals") or ["unspecified signal"])[0]
    title = f"{family['id']} {family['name']}: {signal}"[:160]
    title = title.replace("'", "")
    return [f"hunt lead add --target <TARGET_ID> --title '{title}'"]


def families_markdown(atlas: dict | None = None) -> str:
    """Compact routing table for help output / briefs."""
    data = atlas or load()
    out = ["family  klass         incidents  usd(parsed)  name"]
    for f in data["families"]:
        out.append(f"{f['id']:<6}  {f['klass']:<12}  {f.get('incidents_total', 0):>9}"
                   f"  ${f.get('loss_usd_parsed', 0):>12,.0f}  {f['name']}")
    return "\n".join(out)
