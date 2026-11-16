#!/bin/bash
# Baut NiimbotB1ProDriver.pkg aus dem Quellcode in src/ und der PPD.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$ROOT_DIR/build"
PKGROOT="$BUILD_DIR/pkgroot"
OUT="$ROOT_DIR/dist/NiimbotB1ProDriver.pkg"
VERSION="${1:-1.1}"

rm -rf "$BUILD_DIR"
mkdir -p "$PKGROOT/usr/local/niimbot-cups"
mkdir -p "$PKGROOT/Library/Printers/Niimbot"
mkdir -p "$ROOT_DIR/dist"

cp "$ROOT_DIR/src/niimbot_protocol.py" "$PKGROOT/usr/local/niimbot-cups/"
cp "$ROOT_DIR/src/niimbot_backend.py" "$PKGROOT/usr/local/niimbot-cups/"
cp "$ROOT_DIR/NiimbotB1Pro.ppd" "$PKGROOT/Library/Printers/Niimbot/"

export COPYFILE_DISABLE=1
pkgbuild \
  --root "$PKGROOT" \
  --scripts "$ROOT_DIR/scripts" \
  --identifier de.adrianhinte.niimbot-b1pro-driver \
  --version "$VERSION" \
  --install-location / \
  "$OUT"

echo "Fertig: $OUT"
