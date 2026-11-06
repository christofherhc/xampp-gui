#!/usr/bin/env bash
# =============================================================================
# Desinstalador de XAMPP Control Center del menú de aplicaciones
# =============================================================================
set -e

APP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"

echo "Desinstalando acceso directo de XAMPP Control Center..."

rm -f "$APP_DIR/xampp-control-center.desktop"
rm -f "$ICON_DIR/xampp-control-center.svg"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APP_DIR" 2>/dev/null || true
fi

echo "✔ Acceso directo e icono desinstalados correctamente."
