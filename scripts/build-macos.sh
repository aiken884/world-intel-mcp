#!/usr/bin/env bash
# Build the macOS onedir executable: dist/world-intel/world-intel
# Usage: scripts/build-macos.sh   (requires uv; builds on this machine's arch)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
VENV="$ROOT/.venv-build"
PYVER="${PYVER:-3.12}"

uv venv --clear --python "$PYVER" "$VENV"
uv pip install --python "$VENV/bin/python" -e ".[dashboard]" pyinstaller

rm -rf "$ROOT/build" "$ROOT/dist"
"$VENV/bin/pyinstaller" \
  --noconfirm --clean --onedir \
  --name world-intel \
  --specpath "$ROOT/build" \
  --paths "$ROOT/src" \
  --collect-submodules world_intel_mcp \
  --collect-data world_intel_mcp \
  --collect-submodules mcp.server \
  --collect-submodules mcp.shared \
  --exclude-module mcp.cli \
  --collect-submodules uvicorn \
  --collect-submodules starlette \
  --collect-submodules feedparser \
  --hidden-import dotenv \
  --exclude-module fastembed \
  --exclude-module qdrant_client \
  --exclude-module weasyprint \
  --exclude-module world_intel_mcp.tests \
  "$ROOT/packaging/world_intel_entry.py"

echo "Built: $ROOT/dist/world-intel/world-intel"
file "$ROOT/dist/world-intel/world-intel"
