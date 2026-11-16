#!/bin/bash
# Entfernt den Niimbot-B1-Pro-Treiber vollstaendig: CUPS-Warteschlange,
# Backend, venv, PPD und die Installer-Quittung (pkgutil-Receipt).
set -euo pipefail

PRINTER_NAME="NiimbotB1Pro"
INSTALL_DIR="/usr/local/niimbot-cups"
BACKEND_DEST="/usr/libexec/cups/backend/niimbot"
PPD_DIR="/Library/Printers/Niimbot"
PKG_ID="de.adrianhinte.niimbot-b1pro-driver"

if [ "$(id -u)" -ne 0 ]; then
  echo "Bitte mit sudo ausfuehren: sudo ./uninstall.sh"
  exit 1
fi

echo "-- Druckerwarteschlange entfernen --"
if lpstat -p "$PRINTER_NAME" >/dev/null 2>&1; then
  lpadmin -x "$PRINTER_NAME"
  echo "   $PRINTER_NAME entfernt."
else
  echo "   keine Warteschlange '$PRINTER_NAME' vorhanden."
fi

echo "-- Dateien entfernen --"
rm -f "$BACKEND_DEST"
rm -rf "$INSTALL_DIR"
rm -rf "$PPD_DIR"

echo "-- Installer-Quittung entfernen --"
if pkgutil --pkg-info "$PKG_ID" >/dev/null 2>&1; then
  pkgutil --forget "$PKG_ID"
fi

echo "Fertig. Der Niimbot-Treiber wurde vollstaendig entfernt."
