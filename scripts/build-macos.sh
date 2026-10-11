#!/usr/bin/env bash
# Build the macOS onedir executable: dist/world-intel/world-intel
# Usage: scripts/build-macos.sh   (requires uv; builds on this machine's arch)
#
# The frozen executables read API keys from dist/world-intel/.env, and the
# build wipes dist/. That file is backed up before the wipe and restored after
# a successful build, so a rebuild never silently drops the keys.
#
# The main flow is guarded (BASH_SOURCE == $0) so tests can `source` this file
# and call the helpers on their own.
set -euo pipefail

# backup_dist_env <dist-dir> <backup-file>
# Copies <dist-dir>/world-intel/.env to <backup-file> (mode preserved).
# No .env (or no dist dir) is not an error: nothing is written.
backup_dist_env() {
  local dist="$1" backup="$2"
  if [[ -f "$dist/world-intel/.env" ]]; then
    cp -p "$dist/world-intel/.env" "$backup"
  fi
}

# restore_dist_env <dist-dir> <backup-file>
# Puts the backup back as <dist-dir>/world-intel/.env (mode preserved).
# No backup file is not an error.
restore_dist_env() {
  local dist="$1" backup="$2"
  if [[ -f "$backup" ]]; then
    mkdir -p "$dist/world-intel"
    cp -p "$backup" "$dist/world-intel/.env"
  fi
}

main() {
  local ROOT VENV PYVER ENV_BACKUP_DIR
  ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  cd "$ROOT"
  VENV="$ROOT/.venv-build"
  PYVER="${PYVER:-3.12}"

  ENV_BACKUP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/world-intel-env.XXXXXX")"
  backup_dist_env "$ROOT/dist" "$ENV_BACKUP_DIR/.env"
  # If the build dies after dist/ is wiped, tell the user where the keys are.
  trap 'echo "build failed; dist/world-intel/.env backup kept at $ENV_BACKUP_DIR/.env" >&2' ERR

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

  restore_dist_env "$ROOT/dist" "$ENV_BACKUP_DIR/.env"
  rm -rf "$ENV_BACKUP_DIR"
  trap - ERR

  echo "Built: $ROOT/dist/world-intel/world-intel"
  file "$ROOT/dist/world-intel/world-intel"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
