#!/usr/bin/env bash
# Build the macOS app bundle: dist/World Intel.app (dashboard in a native window).
# Usage: scripts/build-macos-app.sh   (requires uv; builds on this machine's arch)
#
# Separate from scripts/build-macos.sh (CLI/MCP onedir, dist/world-intel/): the
# two outputs live side by side, and this script only touches
# "dist/World Intel.app" plus its own build directory (build/app/).
#
# The main flow is guarded (BASH_SOURCE == $0) so tests can `source` this file
# and call the helpers on their own.
set -euo pipefail

BUNDLE_ID="asia.megapower.world-intel"
APP_NAME="World Intel"

# project_version <pyproject.toml>: the [project] version string.
project_version() {
  sed -n 's/^version = "\(.*\)"$/\1/p' "$1" | head -n 1
}

# patch_info_plist <Info.plist> <version>
patch_info_plist() {
  local plist="$1" version="$2"
  plutil -replace CFBundleShortVersionString -string "$version" "$plist"
  plutil -replace CFBundleVersion -string "$version" "$plist"
  plutil -replace NSHighResolutionCapable -bool true "$plist"
  plutil -replace NSAppTransportSecurity -json '{"NSAllowsLocalNetworking": true}' "$plist"
  plutil -replace LSMinimumSystemVersion -string "12.0" "$plist"
}

main() {
  local ROOT VENV PYVER VERSION APP WORK
  ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  cd "$ROOT"
  VENV="$ROOT/.venv-app"
  PYVER="${PYVER:-3.12}"
  VERSION="$(project_version "$ROOT/pyproject.toml")"
  APP="$ROOT/dist/$APP_NAME.app"
  WORK="$ROOT/build/app"

  if [[ -z "$VERSION" ]]; then
    echo "cannot read the version from pyproject.toml" >&2
    exit 1
  fi
  [[ -f "$ROOT/packaging/AppIcon.icns" ]] || { echo "missing packaging/AppIcon.icns (run packaging/make-icon.sh)" >&2; exit 1; }
  trap 'echo "app build failed; see the output above (build dir: $WORK)" >&2' ERR

  uv venv --clear --python "$PYVER" "$VENV"
  UV_PROJECT_ENVIRONMENT="$VENV" uv sync --locked --python "$PYVER" --extra dashboard --extra gui --group build

  # Only our own outputs; dist/world-intel/ (CLI build) is left alone.
  rm -rf "$WORK" "$APP" "$ROOT/dist/$APP_NAME"
  mkdir -p "$ROOT/dist"
  "$VENV/bin/pyinstaller" \
    --noconfirm --clean --windowed --onedir \
    --name "$APP_NAME" \
    --osx-bundle-identifier "$BUNDLE_ID" \
    --icon "$ROOT/packaging/AppIcon.icns" \
    --distpath "$ROOT/dist" \
    --workpath "$WORK/work" \
    --specpath "$WORK" \
    --paths "$ROOT/src" \
    --collect-submodules world_intel_mcp \
    --collect-data world_intel_mcp \
    --collect-submodules mcp.server \
    --collect-submodules mcp.shared \
    --exclude-module mcp.cli \
    --collect-submodules uvicorn \
    --collect-submodules starlette \
    --collect-submodules feedparser \
    --collect-all webview \
    --hidden-import dotenv \
    --exclude-module fastembed \
    --exclude-module qdrant_client \
    --exclude-module weasyprint \
    --exclude-module world_intel_mcp.tests \
    "$ROOT/packaging/world_intel_app_entry.py"

  # PyInstaller also leaves a plain onedir folder next to the .app; drop it.
  rm -rf "$ROOT/dist/$APP_NAME"

  patch_info_plist "$APP/Contents/Info.plist" "$VERSION"
  codesign --force --deep --sign - "$APP"
  codesign --verify --deep --strict "$APP"
  trap - ERR

  echo "Built: $APP (version $VERSION, ad-hoc signed)"
  du -sh "$APP"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
