#!/usr/bin/env bash
# Package dist/World Intel.app into dist/World-Intel-<version>-arm64.dmg
# (the app plus an /Applications shortcut, for drag-and-drop install).
# Usage: scripts/make-dmg.sh      (run scripts/build-macos-app.sh first)
#
# Idempotent: an existing DMG of the same version is replaced.
set -euo pipefail

APP_NAME="World Intel"

# project_version <pyproject.toml>: the [project] version string.
project_version() {
  sed -n 's/^version = "\(.*\)"$/\1/p' "$1" | head -n 1
}

# dmg_name <version> <arch>
dmg_name() {
  echo "World-Intel-$1-$2.dmg"
}

main() {
  local ROOT VERSION ARCH APP DMG STAGE
  ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  VERSION="$(project_version "$ROOT/pyproject.toml")"
  ARCH="$(uname -m)"
  APP="$ROOT/dist/$APP_NAME.app"
  DMG="$ROOT/dist/$(dmg_name "$VERSION" "$ARCH")"

  if [[ ! -d "$APP" ]]; then
    echo "missing $APP; run scripts/build-macos-app.sh first" >&2
    exit 1
  fi

  STAGE="$(mktemp -d "${TMPDIR:-/tmp}/world-intel-dmg.XXXXXX")"
  # Expanded now: STAGE is local to main and gone by the time EXIT fires.
  # shellcheck disable=SC2064
  trap "rm -rf '$STAGE'" EXIT

  # ditto keeps the ad-hoc signature, symlinks and extended attributes intact.
  ditto "$APP" "$STAGE/$APP_NAME.app"
  ln -s /Applications "$STAGE/Applications"

  rm -f "$DMG"
  hdiutil create -volname "$APP_NAME" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null

  echo "Built: $DMG"
  du -sh "$DMG"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
