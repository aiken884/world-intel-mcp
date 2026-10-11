#!/usr/bin/env bash
# Regenerate packaging/AppIcon.icns from docs/dashboard.png (placeholder icon:
# a centred square crop of the dashboard screenshot).
# Usage: packaging/make-icon.sh [source.png]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${1:-$ROOT/docs/dashboard.png}"
OUT="$ROOT/packaging/AppIcon.icns"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/world-intel-icon.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

read -r W H < <(sips -g pixelWidth -g pixelHeight "$SRC" | awk '/pixel/{print $2}' | xargs)
SIDE=$(( W < H ? W : H ))
sips -c "$SIDE" "$SIDE" "$SRC" --out "$WORK/square.png" >/dev/null

ICONSET="$WORK/AppIcon.iconset"
mkdir "$ICONSET"
for base in 16 32 128 256 512; do
  sips -z "$base" "$base" "$WORK/square.png" --out "$ICONSET/icon_${base}x${base}.png" >/dev/null
  dbl=$(( base * 2 ))
  sips -z "$dbl" "$dbl" "$WORK/square.png" --out "$ICONSET/icon_${base}x${base}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$OUT"
echo "Wrote $OUT"
