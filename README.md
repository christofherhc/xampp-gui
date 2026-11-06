# 🚀 XAMPP Control Center for Linux

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Linux%20(Mint%20%7C%20Ubuntu%20%7C%20Debian)-orange.svg)](https://linuxmint.com/)
[![GUI](https://img.shields.io/badge/GUI-Tkinter%20%2F%20ttk-green.svg)]()
[![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)
[![Security](https://img.shields.io/badge/security-hardened%20(pkexec)-success.svg)]()

**XAMPP Control Center** es un panel de control gráfico, moderno, reactivo y ligero para gestionar la suite **XAMPP (`/opt/lampp`)** en distribuciones Linux (optimizado para Linux Mint, Ubuntu, Debian y derivadas).

Desarrollado en Python con Tkinter nativo, ofrece una alternativa rápida, personalizable y segura frente al gestor oficial de XAMPP, eliminando bloqueos de interfaz, problemas de renderizado en temas oscuros y riesgos de seguridad en la elevación de privilegios.

---

## 📸 Vista Previa

```
┌──────────────────────────────────────────────────────┐
│                XAMPP Control Center                  │
├──────────────────────────────────────────────────────┤
│  Estado de Servicios:                                │
│    Apache:  ● Activo                                 │
│    MySQL:   ● Activo                                 │
│    PHP 8.2.12                       [🔄 Actualizar]  │
├──────────────────────────────────────────────────────┤
│  Servicios Individuales                              │
│    Apache:  ● Activo    [ Iniciar ] [⏹ Detener] [🔄] │
│    MySQL:   ● Activo    [ Iniciar ] [⏹ Detener] [🔄] │
├──────────────────────────────────────────────────────┤
│  Acciones Globales                                   │
│    [▶ Iniciar Todos]  [⏹ Detener Todos]  [🔄 Reiniciar]│
├──────────────────────────────────────────────────────┤
│  Mis Proyectos (htdocs)                              │
│    Proyecto: [ mi-sitio-web       ▼ ] [🔄] [➕]       │
│    [✏ Editor]   [💻 Terminal]   [🌐 Navegador] [📁]   │
├──────────────────────────────────────────────────────┤
│  Navegación y Proyectos                              │
│    [🌐 Localhost]    [🗄 phpMyAdmin]    [📁 Ver htdocs] │
├──────────────────────────────────────────────────────┤
│  Configuraciones Rápidas                             │
│    [⚙ php.ini]      [⚙ httpd.conf]      [⚙ my.cnf]   │
├──────────────────────────────────────────────────────┤
│  Registros / Logs                                    │
│    [📜 Error Log]   [📜 PHP Error Log]  [📝 Log App] │
└──────────────────────────────────────────────────────┘
```

---

## ✨ Características Principales

### 🛡️ Detección de Servicios en 3 Capas con Protección Anti-Colisión
A diferencia de los paneles tradicionales que dependen únicamente del archivo PID o de un script bash, este control center implementa una verificación multicapa que distingue con precisión los binarios de XAMPP de los servicios del sistema:
1. **Capa 1 (Archivos PID Verificados):** Lectura del archivo `.pid` y comprobación en `/proc/<pid>/exe` y `/proc/<pid>/cmdline` para garantizar que pertenezca a `/opt/lampp` y descartar PIDs reciclados tras reinicios.
2. **Capa 2 (Inspección de Procesos en `/opt/lampp`):** Detección dirigida con `pgrep` sobre procesos de `/opt/lampp`, evitando falsos positivos causados por paquetes nativos de la distribución (como `apache2` o `mariadb-server`).
3. **Capa 3 (Sondeo TCP y Detección de Conflictos):** Verificación de conectividad en los puertos locales (80, 3306, 21). Si un puerto responde pero no pertenece a XAMPP, la interfaz advierte inmediatamente: **`⚠️ Conflicto`**.

### 🎛️ Máquina de Estados y Botones Inteligentes
- **Estados Dinámicos:** Los botones se adaptan al estado real del servicio (se desactiva *Iniciar* si ya está corriendo; se desactivan *Detener* y *Reiniciar* si está inactivo o en conflicto ajeno).
- **Prevención de Concurrencia:** Bloqueo reactivo de botones durante la ejecución de tareas para evitar colisiones entre comandos.
- **Acciones Globales Atómicas:** Permite iniciar, detener o reiniciar todos los servicios con una sola solicitud de credenciales Polkit (`pkexec`).

### 📂 Gestor Integrado de Proyectos (`htdocs`)
- **Escaneo Inteligente:** Lista las carpetas en `/opt/lampp/htdocs` filtrando automáticamente carpetas internas de sistema (como `img` o `webalizer`).
- **Creación Rápida (`➕`):** Crea un nuevo proyecto web directamente desde la GUI con validación de seguridad contra path traversal.
- **Abrir en Editor (`✏`):** Abre el proyecto completo en tu IDE o editor configurado (VS Code, Sublime Text, Gedit, Kate, etc.).
- **Abrir Terminal (`💻`):** Lanza tu emulador de terminal favorito (`alacritty`, `kitty`, `gnome-terminal`, `konsole`, `tilix`, etc.) ubicado automáticamente en la raíz del proyecto.
- **Abrir en Navegador (`🌐`):** Abre `http://localhost/<proyecto>` en tu navegador predeterminado con comprobación previa de salud de Apache.
- **Explorar Carpeta (`📁`):** Abre la carpeta específica del proyecto en el gestor de archivos del sistema.

### ⚙️ Accesos Directos a Configuración y Logs
- Edición inmediata en un clic de los archivos principales de XAMPP:
  - `php.ini` (`/opt/lampp/etc/php.ini`)
  - `httpd.conf` (`/opt/lampp/etc/httpd.conf`)
  - `my.cnf` (`/opt/lampp/etc/my.cnf`)
- Detección de permisos de escritura para alertar si el archivo requiere elevación de privilegios.
- Acceso directo a los logs del servidor web: `error_log` y `php_error_log`.
- **Visualizador Interno de Logs:** Visor gráfico con búsqueda de texto en tiempo real con resaltado, filtrado, exportación a archivo `.log`, copia al portapapeles y rotación automática (hasta 1 MB con 5 ciclos de respaldo).

### 🎨 Temas, Ergonomía y Atajos de Teclado
- **Modos Oscuro y Claro:** Paleta moderna inspirada en Catppuccin, garantizando legibilidad y contraste.
- **Centrado Automático:** La ventana principal se posiciona perfectamente centrada en el monitor del usuario al iniciar.
- **Atajos de Teclado Globales:**
  - `F5` / `Ctrl+R`: Actualizar estado de servicios y lista de proyectos.
  - `Ctrl+Q` / `Ctrl+W`: Cerrar la aplicación de manera ordenada.
  - `Ctrl+Shift+S`: Iniciar todos los servicios.
  - `Ctrl+Shift+X`: Detener todos los servicios.
- **Rendimiento Optimizado:** Caché de versión de PHP para evitar crear procesos hijo innecesarios cada 4 segundos.

### 🔒 Seguridad Endurecida
- **Zero Shell Injection:** Todas las llamadas al sistema usan listas de argumentos con `subprocess.run(shell=False)`.
- **Elevación Segura de Privilegios:** Uso exclusivo de `pkexec` (Polkit).
- **Entorno X11 Aislado:** El panel oficial se ejecuta sin habilitar `xhost +` (evitando riesgos de keylogging o captura de pantalla en X11).
- **Permisos de Archivos:** Las preferencias y logs internos se protegen automáticamente con permisos restrictivos `0600`.

---

## 📋 Requisitos del Sistema

- **Sistema Operativo:** Distribución Linux (Linux Mint 20+, Ubuntu 20.04+, Debian 11+ o derivadas).
- **XAMPP para Linux:** Instalado en la ruta estándar `/opt/lampp/`.
- **Python:** Versión 3.8 o superior.
- **Tkinter para Python 3:**
  ```bash
  sudo apt install python3-tk
  ```
- **Herramientas del sistema:** `policykit-1` (o `polkitd`), `procps` (`pgrep`), `xdg-utils` y `libnotify-bin`.

---

## 📥 Instalación

### 1. Clonar el repositorio
```bash
git clone https://github.com/christofherhc/xampp-gui.git ~/.local/bin/xampp-gui
cd ~/.local/bin/xampp-gui
```

### 2. Dar permisos de ejecución
```bash
chmod +x xampp-gui.py
```

### 3. Crear el lanzador de escritorio (.desktop)
Para integrar la aplicación en el menú de aplicaciones de tu entorno de escritorio (Cinnamon, GNOME, XFCE, MATE, KDE):

```bash
mkdir -p ~/.local/share/applications

cat << 'EOF' > ~/.local/share/applications/xampp-control.desktop
[Desktop Entry]
Version=1.0
Type=Application
Name=XAMPP Control Center
Comment=Panel de control para XAMPP
Exec=python3 /home/chris/.local/bin/xampp-gui/xampp-gui.py
Icon=/opt/lampp/htdocs/favicon.ico
Terminal=false
Categories=Development;WebDevelopment;IDE;
StartupNotify=false
EOF
```

> **Nota:** Si tu usuario no es `chris`, ajusta la ruta del parámetro `Exec` con tu usuario actual: `Exec=python3 /home/$USER/.local/bin/xampp-gui/xampp-gui.py`.

Actualiza la base de datos de aplicaciones de tu escritorio:
```bash
update-desktop-database ~/.local/share/applications/
```

---

## 🚀 Uso

Puedes iniciar la aplicación desde tu menú de inicio buscando **"XAMPP Control Center"**, o directamente desde la terminal:

```bash
python3 ~/.local/bin/xampp-gui/xampp-gui.py
```

### Atajos y Flujo de Trabajo
1. **Control de Servicios:** Presiona **"Iniciar Todos"** o los botones individuales para activar Apache o MySQL.
2. **Seleccionar Proyecto:** Selecciona la carpeta de tu sitio web en el desplegable de **Mis Proyectos**.
3. **Desarrollar:** Presiona **Editor** para comenzar a codificar, **Terminal** para ejecutar scripts/artisan/npm, y **Navegador** para visualizarlo al instante.

---

## ⚡ Configuración Opcional: Polkit sin contraseña

Si deseas que `pkexec` no solicite la contraseña de administrador cada vez que inicias o detienes los servicios de XAMPP, puedes crear una regla de Polkit:

Crea el archivo `/etc/polkit-1/rules.d/49-xampp.rules`:
```javascript
/* Permitir gestionar XAMPP sin solicitar contraseña al grupo sudo */
polkit.addRule(function(action, subject) {
    if (action.id == "org.freedesktop.policykit.exec" &&
        action.lookup("program") == "/opt/lampp/lampp" &&
        subject.isInGroup("sudo")) {
        return polkit.Result.YES;
    }
});
```

*(Requiere reiniciar el servicio de Polkit o reiniciar la sesión).*

---

## 🔧 Solución de Problemas Frecuentes

### 1. "Apache no inicia" o "Puerto 80 ocupado"
En distribuciones como Ubuntu o Debian, es común tener el paquete nativo `apache2` instalado e iniciado automáticamente.
```bash
# Comprobar si el apache del sistema está activo
sudo systemctl status apache2

# Detenerlo y deshabilitarlo para liberar el puerto 80
sudo systemctl stop apache2
sudo systemctl disable apache2
```

### 2. Permisos de escritura en `/opt/lampp/htdocs`
Si tu usuario no puede crear o modificar archivos dentro de `htdocs`:
```bash
# Asignar a tu usuario como propietario del directorio htdocs
sudo chown -R $USER:$USER /opt/lampp/htdocs
sudo chmod -R 755 /opt/lampp/htdocs
```

### 3. Error `No module named '_tkinter'`
Instala el paquete Tkinter para Python 3:
```bash
sudo apt update && sudo apt install -y python3-tk
```

---

## 📂 Estructura del Proyecto

```
xampp-gui/
├── xampp-gui.py           # Código fuente principal de la aplicación GUI
├── xampp-gui-prefs.json   # Archivo de configuración local de preferencias de usuario
├── debug.log              # Log de eventos internos de la aplicación (con rotación)
└── README.md              # Documentación oficial
```

---

## 🤝 Contribuciones

¡Las contribuciones son bienvenidas! Si deseas agregar nuevas características, compatibilidad con otros servicios o mejoras de interfaz:
1. Haz un Fork del proyecto.
2. Crea una rama para tu feature (`git checkout -b feature/nueva-mejora`).
3. Realiza tus cambios y haz commit (`git commit -m 'Agregar nueva mejora'`).
4. Sube tu rama (`git push origin feature/nueva-mejora`).
5. Abre un **Pull Request**.

---

## 📄 Licencia

Distribuido bajo la licencia **GNU General Public License v3.0 (GPL-3.0)**. Consulta el archivo de licencia correspondiente para más detalles.

---

Desarrollado con ❤️ para la comunidad de desarrolladores en Linux.
