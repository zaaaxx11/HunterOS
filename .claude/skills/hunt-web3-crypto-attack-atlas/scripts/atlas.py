#!/usr/bin/env python3
"""Standalone reader for the crypto-attack atlas (no package install needed).

For harnesses that read skills by path instead of running the `hunt` CLI:

  python3 scripts/atlas.py list [--klass Oracle]
  python3 scripts/atlas.py show A7
  python3 scripts/atlas.py match "share price jumps on deposit"
  python3 scripts/atlas.py klass

Read-only by construction: it prints, it never writes a ledger or a file.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ATLAS = Path(__file__).resolve().parent.parent / "data" / "atlas.json"


def load() -> dict:
    try:
        with open(ATLAS, encoding="utf-8") as f:
            return json.load(f)
    except OSError as exc:
        sys.exit(f"BLOCKED: atlas data missing at {ATLAS} ({exc})")
    except json.JSONDecodeError as exc:
        sys.exit(f"BLOCKED: atlas data corrupt at {ATLAS} ({exc})")


def find(data: dict, ref: str) -> dict | None:
    want = (ref or "").strip().lower()
    for f in data["families"]:
        if want in (f["id"].lower(), f.get("family", "").lower(), f["name"].lower()):
            return f
    if want.startswith("a") and want[1:].isdigit():
        return find(data, f"A{int(want[1:])}")
    return None


def cmd_list(data: dict, klass: str | None) -> int:
    rows = data["families"]
    if klass:
        rows = [f for f in rows if f["klass"].lower() == klass.lower()]
        if not rows:
            print(f"(no family files under klass '{klass}')")
            return 0
    print(f"{'family':<7} {'klass':<12} {'incidents':>9} {'usd(parsed)':>14}  name")
    for f in rows:
        print(f"{f['id']:<7} {f['klass']:<12} {f.get('incidents_total', 0):>9} "
              f"${f.get('loss_usd_parsed', 0):>13,.0f}  {f['name']}")
    return 0


def cmd_show(data: dict, ref: str) -> int:
    f = find(data, ref)
    if f is None:
        print(f"(no family matches '{ref}' — try: list)")
        return 1
    print(f"{f['id']} — {f['name']}   (klass: {f['klass']})")
    print(f"\n{f['summary']}")
    print(f"\nincidents: {f.get('incidents_total', 0)} | "
          f"usd parsed: ${f.get('loss_usd_parsed', 0):,.0f} (lower bound)")
    if f.get("swc"):
        print("swc: " + ", ".join(f"{s['id']} {s['title']}" for s in f["swc"]))
    if f.get("skills"):
        print("skills: " + ", ".join(f["skills"]))
    for label, key in (("VARIANTS", "variants"), ("SIGNALS", "signals"),
                       ("DETECT", "detect"), ("MITIGATE", "mitigate")):
        items = f.get(key) or []
        if items:
            print(f"\n{label}")
            for it in items:
                print(f"  - {it}")
    if f.get("examples"):
        print("\nREAL CASES")
        for ex in f["examples"]:
            amt = f"${ex['loss_usd']:,.0f}" if ex["loss_usd"] else (ex["loss_raw"] or "n/a")
            print(f"  - {ex['date']} {ex['target']} — {amt}{' (PoC)' if ex['poc'] else ''}")
    return 0


def cmd_match(data: dict, text: str, top: int) -> int:
    words = (text or "").lower()
    scored = []
    for f in data["families"]:
        hits = [k for k in data.get("keywords", {}).get(f["id"], []) if k in words]
        if hits:
            scored.append((len(hits), f, hits))
    if not scored:
        print("(no family matched — describe the observable, or run: list)")
        return 1
    scored.sort(key=lambda t: (-t[0], t[1]["id"]))
    for n, f, hits in scored[:top]:
        print(f"{f['id']} {f['name']}  ({f['klass']}, {n} hit)")
        print(f"  matched: {', '.join(hits)}")
        print(f"  next: python3 scripts/atlas.py show {f['id']}")
    return 0


def cmd_klass(data: dict) -> int:
    seen = []
    for f in data["families"]:
        if f["klass"] not in seen:
            seen.append(f["klass"])
    for k in seen:
        ids = ", ".join(f["id"] for f in data["families"] if f["klass"] == k)
        print(f"{k:<12} {ids}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="atlas.py", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("list", help="list families")
    pl.add_argument("--klass", default=None)
    ps = sub.add_parser("show", help="show one family")
    ps.add_argument("ref")
    pm = sub.add_parser("match", help="rank families against a symptom")
    pm.add_argument("text", nargs="+")
    pm.add_argument("--top", type=int, default=3)
    sub.add_parser("klass", help="klass -> families")
    a = p.parse_args(argv)
    data = load()
    if a.cmd == "list":
        return cmd_list(data, a.klass)
    if a.cmd == "show":
        return cmd_show(data, a.ref)
    if a.cmd == "match":
        return cmd_match(data, " ".join(a.text), a.top)
    return cmd_klass(data)


if __name__ == "__main__":
    sys.exit(main())