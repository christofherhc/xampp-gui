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

### 📂 Gestor Integrado de Proyectos (`htdocs`) con Detección de Frameworks
- **Detección Automática de Frameworks:** Analiza la tecnología del proyecto y muestra una insignia visual inmediata:
  - ⚡ **Laravel:** Reconocimiento de `artisan`; el botón **Navegador** redirige automáticamente a `http://localhost/<proyecto>/public`.
  - 📰 **WordPress:** Reconocimiento de `wp-config.php`, `wp-content`, etc.
  - ▲ **Next.js** y 📦 **Node.js:** Reconocimiento de `package.json` y configuraciones.
  - 🐍 **Django** y **Python:** Reconocimiento de `manage.py`, `requirements.txt`, etc.
  - 🐘 **Composer / PHP:** Proyectos PHP tradicionales.
  - 🌐 **HTML:** Proyectos estáticos con `index.html`.
- **Escaneo Inteligente:** Lista las carpetas en `/opt/lampp/htdocs` filtrando automáticamente carpetas internas de sistema (como `img` o `webalizer`).
- **Creación Rápida (`➕`):** Crea un nuevo proyecto web directamente desde la GUI con validación de seguridad contra path traversal.
- **Abrir en Editor (`✏`):** Abre el proyecto completo en tu IDE o editor configurado (VS Code, Sublime Text, Gedit, Kate, etc.).
- **Abrir Terminal (`💻`):** Lanza tu emulador de terminal favorito (`alacritty`, `kitty`, `gnome-terminal`, `konsole`, `tilix`, etc.) ubicado automáticamente en la raíz del proyecto.
- **Abrir en Navegador (`🌐`):** Abre `http://localhost/<proyecto>` en tu navegador predeterminado con comprobación previa de salud de Apache.
- **Explorar Carpeta (`📁`):** Abre la carpeta específica del proyecto en el gestor de archivos del sistema.

### 🐬 Herramientas Rápidas de Base de Datos (MySQL)
Desde el nuevo menú **Base de Datos** en la barra superior:
- **Crear Nueva Base de Datos:** Diálogo asistido con validación estricta de nombres y codificación predeterminada `utf8mb4` / `utf8mb4_unicode_ci`.
- **Consola MySQL en Terminal:** Lanza una consola interactiva oficial de MySQL (`/opt/lampp/bin/mysql -u root`) dentro de tu emulador de terminal preferido.
- **Exportar Respaldo (.sql):** Selector interactivo de bases de datos que ejecuta `mysqldump` en segundo plano con flags de nivel producción (`--single-transaction`, `--routines`, `--triggers`, UTF-8).
- **Importar Respaldo (.sql):** Asistente para seleccionar un archivo `.sql` e importarlo en streaming a la base de datos de tu elección (con opción automática de crear la base de datos si no existe).

### 🧹 Herramientas de Mantenimiento y Janitor
Desde el nuevo menú **Herramientas**:
- **Purga de Logs del Servidor:** Identifica y muestra el tamaño total de los archivos de registro (`access_log`, `error_log`, `php_error_log`, etc.) y permite truncarlos con confirmación previa y elevación Polkit transparente.
- **Limpieza de Sesiones Temporales:** Escanea y elimina archivos de sesión huérfanos (`sess_*`) acumulados en `/opt/lampp/temp`.
- **Diagnóstico del Entorno y Disco:** Monitor visual del almacenamiento de la partición de XAMPP con barra de uso y verificación de permisos de escritura en `/opt/lampp/htdocs` con la sugerencia de comando de corrección para tu usuario.
- **Ajustes Rápidos de PHP (php.ini):** Modal gráfico para inspeccionar y ajustar de forma segura directivas críticas (`upload_max_filesize`, `post_max_size`, `memory_limit`, `max_execution_time`) creando una copia de seguridad automática (`php.ini.bak`).

### 🌐 Administrador Gráfico de Virtual Hosts (VHosts)
Permite configurar y gestionar dominios locales personalizados (ej. `misitio.test`, `laravel.local`) sin editar archivos manualmente en la terminal:
- **Habilitación con 1 Clic:** Detecta si la directiva `Include etc/extra/httpd-vhosts.conf` está activa en `/opt/lampp/etc/httpd.conf` y ofrece habilitarla automáticamente con respaldo (`httpd.conf.bak`).
- **Asistente Guiado de Creación:**
  - Validación de nombre de dominio contra caracteres inválidos.
  - Vinculación a proyectos de `htdocs` o selección de carpeta personalizada mediante explorador.
  - **Soporte Inteligente para Laravel:** Detecta si existe la carpeta `/public` y la asigna automáticamente como `DocumentRoot`.
  - **Sincronización con `/etc/hosts`:** Agrega automáticamente `127.0.0.1 dominio www.dominio` mediante Polkit (`pkexec`).
- **Exploración y Eliminación:** Lista en tabla con columnas de dominio, ruta y puerto, botón para abrir directamente en el navegador (`🌐`) y opción para eliminar el Virtual Host junto con la limpieza de su entrada en `/etc/hosts`.

### 🚨 Asistente de Resolución de Conflictos de Puertos
En distribuciones como Linux Mint y Ubuntu es muy común que servicios nativos del sistema como `apache2`, `nginx` o `mariadb` se inicien en el arranque, bloqueando los puertos 80 o 3306 e impidiendo que XAMPP funcione:
- **Detección Automática:** Verifica si los puertos 80 y 3306 están abiertos mientras XAMPP está apagado e identifica el servicio nativo culpable mediante `systemctl is-active`.
- **Resolución con 1 Clic:** Ofrece un botón para detener y deshabilitar el servicio conflictivo del sistema (`pkexec systemctl stop <svc> && pkexec systemctl disable <svc>`), liberando el puerto de forma permanente para XAMPP.

### 🧩 Inspector y Activador de Extensiones de PHP
- **Lectura en Vivo:** Lee los módulos cargados en tiempo real ejecutando `/opt/lampp/bin/php -m`.
- **Módulos Frecuentes:** Monitorea extensiones críticas para el desarrollo web moderno: `curl`, `intl` (Symfony/Laravel), `mbstring`, `openssl`, `pdo_mysql`, `mysqli`, `zip` (Composer), `gd`, `fileinfo`, `bcmath`, `soap`.
- **Activación Gráfica:** Si una extensión está inactiva, un botón **Activar** descomenta o inserta la directiva correspondiente en `/opt/lampp/etc/php.ini` de forma segura mediante elevación Polkit.

### 🔐 Generador de Certificados SSL Locales (HTTPS) y VirtualHosts Seguros
Permite probar aplicaciones web en entornos seguros HTTPS locales (esencial para Progressive Web Apps, Service Workers, geolocalización, cookies seguras `SameSite=None`, WebSockets `wss://` y autenticación moderna):
- **Generación Automática:** Genera pares de Clave Privada RSA (2048-bit) y Certificados X.509 autofirmados con SAN (*Subject Alternative Name*) para `localhost`, dominios locales (`*.test`) y `127.0.0.1` usando `openssl`.
- **Integración con Apache:** Instala los archivos en `/opt/lampp/etc/ssl.crt/` y `/opt/lampp/etc/ssl.key/` y genera automáticamente el bloque `<VirtualHost *:443>` con `SSLEngine on`.
- **Comando de Confianza para Linux Mint:** Proporciona el comando exacto para agregar el certificado a `/usr/local/share/ca-certificates/` y actualizar el almacén con `update-ca-certificates`, eliminando advertencias en Chrome/Firefox.

### 📊 Monitor de Telemetría y Rendimiento en Tiempo Real (CPU, RAM y Conexiones)
Panel visual integrado para supervisar el impacto en el sistema de los servicios de XAMPP:
- **Consumo de Memoria RAM (RSS) y CPU%:** Calcula en tiempo real el consumo individual y total de Apache (`httpd`), MySQL (`mysqld`) y ProFTPD (`proftpd`) leyendo directamente los procesos de `/opt/lampp`.
- **Métricas Avanzadas de Base de Datos:** Reporta en vivo las conexiones simultáneas activas (`Threads_connected`), tiempo de actividad (`Uptime`) y total de consultas procesadas (`Queries`).
- **Actualización Reactiva:** Modo de actualización en vivo cada 2 segundos con parada limpia al cerrar el diálogo.

### 💾 Gestor de Puntos de Restauración (Snapshots & 1-Clic Rollback)
Sistema de protección contra pérdidas de datos y errores de configuración:
- **Instantáneas Completas:** Exporta todas las bases de datos (`mysqldump --all-databases --single-transaction --routines`) y archiva los archivos de configuración (`php.ini`, `httpd.conf`, `httpd-vhosts.conf`, `httpd-ssl.conf`, `my.cnf`) en `~/.local/share/xampp-gui/snapshots/` con metadatos JSON.
- **Rollback con 1 Clic:** Restaura instantáneamente el estado completo de las bases de datos y configuraciones ante experimentos fallidos o migraciones destructivas.
- **Gestión Visual:** Tabla con fecha, descripción, tamaño y opción de eliminación para liberar almacenamiento.

### 🐘 Selector de Entornos PHP Multi-Versión y Lanzador CLI
- **Detección Automática:** Escanea todos los binarios PHP presentes en el sistema Linux Mint (`/opt/lampp/bin/php`, `/usr/bin/php`, `/usr/bin/php7.*`, `/usr/bin/php8.*`).
- **Inspección de Módulos:** Muestra la versión exacta del compilador, motor Zend y cantidad de extensiones activas.
- **Lanzador de Terminal Aislado:** Abre tu terminal favorita con `export PATH="<dir_php>:$PATH"`, permitiéndote ejecutar herramientas de línea de comandos (`composer`, `artisan`, `symfony`, `wp-cli`) con la versión específica de PHP que requiere cada proyecto.

### ⚡ Benchmark de Servidor y Pruebas de Carga (ApacheBench)
Permite auditar el rendimiento y capacidad de respuesta de tus aplicaciones web en Apache:
- **Ejecución Integrada:** Lanza `/opt/lampp/bin/ab` en segundo plano sin congelar la interfaz gráfica.
- **Métricas Clave:** Analiza automáticamente peticiones por segundo (RPS), latencia media (ms), tasa de transferencia (KB/s) y conteo de peticiones fallidas.
- **Reporte Completo:** Muestra el desglose detallado con percentiles de latencia y opción de copiar al portapapeles en 1 clic.

### 🌍 Compartir Proyecto en Internet (Túnel SSH con HTTPS Instantáneo)
Comparte tu servidor local con clientes o prueba webhooks externos (Stripe, PayPal, MercadoPago, GitHub) sin instalar herramientas de terceros como ngrok:
- **Túnel SSH Nativo:** Utiliza el cliente SSH preinstalado en Linux Mint conectando con `nokey@localhost.run` mediante reenvío de puertos reverso (`-R 80:localhost:80`).
- **Detección Automática de URL:** Extrae la URL pública segura (`https://...lhr.life`) y permite copiarla o abrirla en el navegador con un solo clic.
- **Control de Proceso Limpio:** Permite iniciar y detener el túnel en cualquier momento con terminación segura de procesos.

### 📜 Monitor en Vivo de Logs (Live Tail en Tiempo Real)
Monitorea continuamente la actividad de Apache y errores de PHP con flujo continuo tipo `tail -f`:
- **Selector de Origen:** Alterna en vivo entre `Apache Error Log`, `PHP Error Log`, `Apache Access Log` y el `Log de la Aplicación`.
- **Resaltado de Sintaxis por Severidad:**
  - 🔴 **Rojo/Negrita:** Errores fatales, excepciones y fallos críticos.
  - 🟠 **Naranja:** Advertencias (`Warning`), avisos (`Notice`) y funciones en desuso (`Deprecated`).
  - 🔵 **Azul:** Mensajes informativos del servidor.
- **Filtro y Pausa:** Filtrado por palabra clave en tiempo real y botón para pausar/reanudar el flujo de datos.

### 🛠️ Editor y Asistente de Reglas `.htaccess`
Herramienta visual para configurar directivas avanzadas de Apache a nivel de proyecto:
- **Detección Inteligente de Raíz:** Localiza automáticamente `.htaccess` en la raíz del proyecto o dentro de `/public` (para proyectos Laravel).
- **Plantillas Listas para Usar:** Inserta con un clic fragmentos probados para:
  - Enrutamiento de aplicaciones SPA (React, Vue, Angular).
  - Forzar redirección HTTPS automática.
  - Habilitar cabeceras CORS (`Access-Control-Allow-Origin`).
  - Cabeceras de seguridad (`X-Frame-Options`, `X-Content-Type-Options`, `X-XSS-Protection`).
  - Desactivar listado de directorios (`Options -Indexes`).
- **Respaldo Automático:** Genera automáticamente una copia `.bak` antes de escribir cualquier cambio.

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

### 2. Instalar acceso directo en el sistema (Recomendado)
El proyecto incluye un script de instalación automatizado para registrar el icono oficial y el acceso directo en el menú de aplicaciones de tu distribución:

```bash
chmod +x install.sh uninstall.sh xampp-gui.py
./install.sh
```

El instalador:
- Instala el icono vectorial oficial `xampp-control-center.svg` en `~/.local/share/icons/hicolor/scalable/apps/`.
- Configura e instala el archivo de escritorio `xampp-control-center.desktop` en `~/.local/share/applications/`.
- Actualiza la caché del entorno de escritorio automáticamente.

> **Tip:** También puedes instalar o reinstalar el acceso directo en cualquier momento desde la propia aplicación en el menú **Herramientas ➔ Instalar acceso directo en el sistema...**

Para desinstalar el acceso directo y sus iconos en el futuro:
```bash
./uninstall.sh
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
├── xampp-gui.py                # Código fuente principal de la aplicación GUI
├── xampp-control-center.desktop # Entrada de escritorio para el menú de aplicaciones
├── xampp-control-center.svg     # Icono vectorial escalable oficial
├── install.sh                  # Script de instalación e integración en el sistema
├── uninstall.sh                # Script de desinstalación limpia
├── xampp-gui-prefs.json        # Archivo local de preferencias del usuario
├── debug.log                   # Log de eventos internos de la aplicación (con rotación)
└── README.md                   # Documentación oficial
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
