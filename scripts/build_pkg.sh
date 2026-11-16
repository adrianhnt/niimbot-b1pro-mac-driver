#!/bin/bash
# Baut NiimbotB1ProDriver.pkg aus dem Quellcode in src/ und der PPD.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$ROOT_DIR/build"
PKGROOT="$BUILD_DIR/pkgroot"
SCRIPTS_OUT="$BUILD_DIR/scripts"
OUT="$ROOT_DIR/dist/NiimbotB1ProDriver.pkg"
VERSION="${1:-1.1}"

rm -rf "$BUILD_DIR"
mkdir -p "$PKGROOT/usr/local/niimbot-cups"
mkdir -p "$PKGROOT/Library/Printers/Niimbot"
mkdir -p "$SCRIPTS_OUT"
mkdir -p "$ROOT_DIR/dist"

cp "$ROOT_DIR/src/niimbot_protocol.py" "$PKGROOT/usr/local/niimbot-cups/"
cp "$ROOT_DIR/src/niimbot_backend.py" "$PKGROOT/usr/local/niimbot-cups/"
mkdir -p "$PKGROOT/usr/local/niimbot-cups/vendor"
cp -R "$ROOT_DIR/src/vendor/serial" "$PKGROOT/usr/local/niimbot-cups/vendor/serial"
find "$PKGROOT/usr/local/niimbot-cups/vendor" -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
cp "$ROOT_DIR/NiimbotB1Pro.ppd" "$PKGROOT/Library/Printers/Niimbot/"

# Versionsnummer in die Installer-Skripte einsetzen (fuer die
# Schon-installiert-/Update-Erkennung beim naechsten Install).
sed "s/__NIIMBOT_VERSION__/$VERSION/g" "$ROOT_DIR/scripts/preinstall.template" > "$SCRIPTS_OUT/preinstall"
sed "s/__NIIMBOT_VERSION__/$VERSION/g" "$ROOT_DIR/scripts/postinstall.template" > "$SCRIPTS_OUT/postinstall"
chmod +x "$SCRIPTS_OUT/preinstall" "$SCRIPTS_OUT/postinstall"

export COPYFILE_DISABLE=1
pkgbuild \
  --root "$PKGROOT" \
  --scripts "$SCRIPTS_OUT" \
  --identifier de.adrianhinte.niimbot-b1pro-driver \
  --version "$VERSION" \
  --install-location / \
  "$OUT"

echo "Fertig: $OUT"
