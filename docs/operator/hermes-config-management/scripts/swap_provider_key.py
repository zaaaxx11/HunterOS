#!/usr/bin/env python3
"""Swap API key for a named provider in a Hermes config.yaml — line-preserving.

Usage:
    python3 swap_provider_key.py <provider_name> <new_api_key>
    python3 swap_provider_key.py <provider_name> <new_api_key> --config /path/to/config.yaml

Covers BOTH key locations (a provider can exist in one or both):
  1. `providers:` map          -> providers.<name>.api_key      (2-space block, 4-space api_key)
  2. `custom_providers:` list  -> entry whose `  name:` == provider
     NOTE: in this file list entries are shaped `- api_key: ...` (2-space dash),
     then `  base_url:` / `  name:` — so api_key PRECEDES name inside an entry.
     Matching therefore works per-entry-block with lookahead for the name line.

Why line-based instead of yaml.safe_dump: preserves comments/key order/formatting.
Why block-scoped instead of sed 's/api_key/.../': the file has MANY providers,
each with its own api_key line — a blind global replace nukes them all.

Never echoes the key: prints MATCH / MISSING + char length only. Tool output
redacts secrets anyway, and echoing puts the key into shell history/transcripts.
Exit codes: 0 all locations updated, 1 mismatch, 2 provider not found.
"""
import argparse
import datetime
import re
import shutil
import sys

MAP_BLOCK_RE = re.compile(r'^  ([A-Za-z0-9_.-]+):\s*$')            # provider block inside `providers:` map
MAP_KEY_RE = re.compile(r'^    api_key:')                          # 4-space, inside providers map block
LIST_ITEM_RE = re.compile(r'^  - api_key:')                        # entry start in custom_providers list (2-space dash)
LIST_NAME_RE = re.compile(r'^  name:\s*([A-Za-z0-9_.-]+)\s*$')     # 2-space name line inside a list entry


def rotate(path: str, provider: str, new_key: str) -> int:
    lines = open(path).read().splitlines()
    out = list(lines)
    updated = 0
    p = provider.lower()

    # --- section 1: providers: map (simple state machine) ---
    in_map = False
    in_target = False
    for i, line in enumerate(out):
        if re.match(r'^providers:\s*$', line):
            in_map, in_target = True, False
            continue
        if in_map:
            m = MAP_BLOCK_RE.match(line)
            if m:
                in_target = m.group(1).lower() == p
                continue
            if in_target and MAP_KEY_RE.match(line):
                out[i] = '    api_key: ' + new_key
                updated += 1
                in_target = False  # api_key is the only line to touch in this block
                continue
        if line and not line.startswith(' '):
            in_map, in_target = False, False  # left the providers map

    # --- section 2: custom_providers: list (entry-block + name lookahead) ---
    list_start = list_end = None
    for i, line in enumerate(out):
        if re.match(r'^custom_providers:\s*$', line):
            list_start = i
        elif list_start is not None and i > list_start and line and not line.startswith(' '):
            list_end = i
            break
    if list_start is not None:
        if list_end is None:
            list_end = len(out)
        entry_starts = [i for i in range(list_start + 1, list_end) if LIST_ITEM_RE.match(out[i])]
        for idx, start in enumerate(entry_starts):
            end = entry_starts[idx + 1] if idx + 1 < len(entry_starts) else list_end
            block = out[start:end]
            if any(LIST_NAME_RE.match(l) and LIST_NAME_RE.match(l).group(1).lower() == p for l in block):
                out[start] = '  - api_key: ' + new_key  # key line is the first line of the entry
                updated += 1

    if updated == 0:
        print(f'MISSING: no api_key line found for provider "{provider}"')
        return 2
    open(path, 'w').write('\n'.join(out) + '\n')
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('provider')
    ap.add_argument('new_key')
    ap.add_argument('--config', default='/root/.hermes/config.yaml')
    args = ap.parse_args()

    path = args.config
    bak = f'{path}.bak.{args.provider}.{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}'
    shutil.copy2(path, bak)
    print(f'backup: {bak}')

    rc = rotate(path, args.provider, args.new_key)
    if rc != 0:
        return rc

    import yaml
    cfg = yaml.safe_load(open(path))
    found = []
    prov_map = {k.lower(): k for k in (cfg.get('providers') or {})}
    if args.provider.lower() in prov_map:
        found.append(('providers', cfg['providers'][prov_map[args.provider.lower()]].get('api_key') == args.new_key))
    for entry in cfg.get('custom_providers', []) or []:
        if isinstance(entry, dict) and str(entry.get('name', '')).lower() == args.provider.lower():
            found.append(('custom_providers', entry.get('api_key') == args.new_key))
    if not found:
        print(f'WARNING: "{args.provider}" not in providers: map or custom_providers: list')
        return 2
    ok = True
    for loc, ok_ in found:
        print(f'{loc}: {"MATCH" if ok_ else "MISMATCH — check manually"}')
        ok = ok and ok_
    print(f'keylen: {len(args.new_key)}')
    print('YAML: valid')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
