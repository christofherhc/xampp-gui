#!/usr/bin/env bash
# =============================================================================
# Instalador de XAMPP Control Center en el menú de aplicaciones de Linux Mint
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"

echo "Instalando XAMPP Control Center para el usuario actual..."

# Asegurar carpetas XDG
mkdir -p "$APP_DIR"
mkdir -p "$ICON_DIR"

# Instalar icono
if [ -f "$SCRIPT_DIR/xampp-control-center.svg" ]; then
    cp "$SCRIPT_DIR/xampp-control-center.svg" "$ICON_DIR/xampp-control-center.svg"
    echo "✔ Icono instalado en $ICON_DIR/xampp-control-center.svg"
fi

# Generar archivo .desktop dinámico con la ruta absoluta del repositorio
cat <<EOF > "$APP_DIR/xampp-control-center.desktop"
[Desktop Entry]
Version=1.0
Type=Application
Name=XAMPP Control Center
GenericName=Panel de Control XAMPP
Comment=Administrador gráfico de servicios y proyectos para XAMPP en Linux
Exec=python3 "$SCRIPT_DIR/xampp-gui.py"
Icon=xampp-control-center
Terminal=false
Categories=Development;WebDevelopment;System;
StartupNotify=true
Keywords=xampp;lamp;apache;mysql;php;phpmyadmin;
EOF

chmod +x "$APP_DIR/xampp-control-center.desktop"
chmod +x "$SCRIPT_DIR/xampp-gui.py"

# Actualizar base de datos de aplicaciones si la utilidad existe
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APP_DIR" 2>/dev/null || true
fi

echo "✔ Acceso directo creado en $APP_DIR/xampp-control-center.desktop"
echo ""
echo "🎉 ¡Instalación completada! Ahora puedes abrir 'XAMPP Control Center' desde el menú de aplicaciones de Linux Mint (Categoría: Desarrollo / Programación)."
