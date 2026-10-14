#!/bin/bash
# download-nextjs-chunks.sh <base_url> <homepage.html> [outdir]
#
# Downloads every <script src="...js"> chunk referenced by a Next.js homepage.
#
# Why not `xargs -I{} sh -c '...{}...'`? App-router route-group paths contain
# literal shell metacharacters, e.g.
#   /_next/static/chunks/app/%5Blocale%5D/(default)/layout-<hash>.js
# Substituting those into an sh -c string yields:
#   sh: -c: line 1: syntax error near unexpected token `('
# and the chunk (often the juiciest one — the default route's page bundle) is
# silently skipped. This script uses a properly-quoted while-read loop with
# indexed output names, and writes chunk-map.tsv (filename -> source path) so
# later greps can be traced back to the original chunk URL.
set -u

BASE="${1:?usage: download-nextjs-chunks.sh <base_url> <homepage.html> [outdir]}"
HTML="${2:?usage: download-nextjs-chunks.sh <base_url> <homepage.html> [outdir]}"
OUT="${3:-js}"

mkdir -p "$OUT"
LIST="$(mktemp)"
trap 'rm -f "$LIST"' EXIT

grep -oE 'src="[^"]+\.js[^"]*"' "$HTML" | sed -E 's/src="([^"]+)".*/\1/' | sort -u > "$LIST"

: > "$OUT/chunk-map.tsv"
i=0
while IFS= read -r chunk; do
  i=$((i+1))
  out="$OUT/chunk_$(printf '%03d' "$i").js"
  printf '%s\t%s\n' "$out" "$chunk" >> "$OUT/chunk-map.tsv"
  curl -s4 -o "$out" "${BASE}${chunk}" &
  if (( i % 12 == 0 )); then wait; fi
done < "$LIST"
wait

ok=$(find "$OUT" -name 'chunk_*.js' -size +0c | wc -l)
total=$(wc -l < "$LIST")
echo "Downloaded $ok/$total non-empty chunks into $OUT/ (map: $OUT/chunk-map.tsv)"
