import tkinter as tk
from tkinter import messagebox, ttk, scrolledtext
import subprocess
import webbrowser
import os
import datetime
import json
import threading
import socket
import shutil
import re
from urllib.parse import quote
import glob

# Lock para sincronización de escritura y rotación de logs
LOG_LOCK = threading.Lock()

# Ruta del directorio del proyecto
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# Ruta del archivo log interno
LOG_PATH = os.path.join(PROJECT_DIR, "debug.log")
PREFS_PATH = os.path.join(PROJECT_DIR, "xampp-gui-prefs.json")

# Carpeta de proyectos web de XAMPP
HTDOCS_PATH = "/opt/lampp/htdocs"

# Temas de colores
THEMES = {
    "dark": {
        "bg": "#1e1e2e",
        "bg_secondary": "#11111b",
        "bg_button": "#313244",
        "bg_button_config": "#45475a",
        "bg_button_log": "#585b70",
        "fg": "#cdd6f4",
        "fg_label": "#89b4fa",
        "fg_status": "#a6e3a1",
        "fg_active": "#a6e3a1",
        "fg_inactive": "#f38ba8",
        "fg_conflict": "#fab387",
        "btn_start": "#28a745",
        "btn_stop": "#dc3545",
        "btn_restart": "#f39c12",
        "btn_start_global": "#2e7d32",
        "btn_stop_global": "#c62828",
        "btn_restart_global": "#d97706",
        "btn_disabled_bg": "#25263a",
        "btn_disabled_fg": "#6c7086",
    },
    "light": {
        "bg": "#eff1f5",
        "bg_secondary": "#e6e9ef",
        "bg_button": "#ccd0da",
        "bg_button_config": "#bcc0cc",
        "bg_button_log": "#acb0be",
        "fg": "#4c4f69",
        "fg_label": "#1e66f5",
        "fg_status": "#40a02b",
        "fg_active": "#40a02b",
        "fg_inactive": "#d20f39",
        "fg_conflict": "#df8e1d",
        "btn_start": "#28a745",
        "btn_stop": "#dc3545",
        "btn_restart": "#f39c12",
        "btn_start_global": "#2e7d32",
        "btn_stop_global": "#c62828",
        "btn_restart_global": "#d97706",
        "btn_disabled_bg": "#dce0e8",
        "btn_disabled_fg": "#9ca0b0",
    }
}

# Editores disponibles
EDITORS = {
    "VS Code": "code",
    "Gedit": "gedit",
    "Sublime Text": "subl",
    "Kate": "kate",
    "Mousepad": "mousepad",
    "Xed": "xed",
    "Nano (terminal)": "nano",
    "Vi/Vim (terminal)": "vi"
}

# Servicios disponibles (se detectan dinámicamente según binarios instalados)
ALL_SERVICES = {
    "Apache": {
        "name": "apache",
        "cmd": "apache",
        "bins": ["bin/httpd", "sbin/httpd"],
        "procs": ["httpd", "httpd.bin", "apache2"],
        "pid_file": "/opt/lampp/logs/httpd.pid",
        "port": 80,
    },
    "MySQL": {
        "name": "mysql",
        "cmd": "mysql",
        "bins": ["bin/mysqld", "sbin/mysqld"],
        "procs": ["mysqld", "mariadbd"],
        "pid_file": None,
        "port": 3306,
    },
    "ProFTPD": {
        "name": "proftpd",
        "cmd": "ftp",
        "bins": ["sbin/proftpd", "bin/proftpd"],
        "procs": ["proftpd"],
        "pid_file": "/opt/lampp/var/proftpd.pid",
        "port": 21,
    },
}

def detect_services():
    """Devuelve dict de servicios realmente instalados en /opt/lampp."""
    services = {}
    for label, info in ALL_SERVICES.items():
        for bin_path in info["bins"]:
            if os.path.exists(os.path.join("/opt/lampp", bin_path)):
                services[label] = info
                break
    return services

SERVICES = detect_services()

def _is_lampp_pid(pid, service_name=None):
    """Comprueba si un PID vivo pertenece a un proceso ejecutado desde /opt/lampp."""
    try:
        exe_path = os.path.realpath(f"/proc/{pid}/exe")
        if "/opt/lampp" in exe_path:
            return True
    except Exception:
        pass
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            cmdline = f.read().decode("utf-8", errors="ignore")
        if "/opt/lampp" in cmdline:
            return True
    except Exception:
        pass
    return False

def detect_service_status(info):
    """Comprueba de forma robusta y en múltiples capas el estado de un servicio.
    Distingue procesos genuinos de XAMPP (/opt/lampp) de servicios del sistema (ej. apache2/mysql nativos).
    Devuelve una tupla: (estado_str, is_conflict)
    - ("● Activo", False): Servicio de XAMPP corriendo correctamente.
    - ("⚠️ Conflicto", True): Puerto ocupado por un servicio ajeno a XAMPP.
    - ("○ Inactivo", False): Servicio detenido y puerto libre.
    """
    service_name = info.get("name", "")
    lampp_running = False

    # Capa 1: Verificación de archivo PID verificado en /proc/<pid>
    pid_files = []
    if info.get("pid_file"):
        pid_files.append(info["pid_file"])
    elif service_name == "mysql":
        mysql_dir = "/opt/lampp/var/mysql"
        if os.path.isdir(mysql_dir):
            try:
                for f in os.listdir(mysql_dir):
                    if f.endswith(".pid"):
                        pid_files.append(os.path.join(mysql_dir, f))
            except Exception:
                pass
        pid_files.append("/opt/lampp/var/my.pid")

    for pf in pid_files:
        if os.path.isfile(pf):
            try:
                with open(pf, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read().strip()
                if content:
                    pid_str = content.split()[0]
                    if pid_str.isdigit():
                        pid = int(pid_str)
                        if os.path.exists(f"/proc/{pid}"):
                            # Validar que pertenezca a XAMPP y no sea un PID reciclado
                            if _is_lampp_pid(pid, service_name):
                                lampp_running = True
                                break
                            elif not os.path.exists(f"/proc/{pid}/exe"):
                                # Si no se puede leer /proc/<pid>/exe por permisos root, pero el PID file de XAMPP existe
                                lampp_running = True
                                break
            except Exception:
                pass

    # Capa 2: Comprobación de procesos de /opt/lampp mediante pgrep
    if not lampp_running and service_name:
        try:
            res = subprocess.run(["pgrep", "-f", f"/opt/lampp.*{service_name}"],
                                 capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                lampp_running = True
        except Exception:
            pass

    if not lampp_running:
        procs = info.get("procs", [])
        for p in procs:
            if not p:
                continue
            try:
                res = subprocess.run(["pgrep", "-x", p], capture_output=True, text=True)
                if res.returncode == 0:
                    for p_str in res.stdout.strip().split():
                        if p_str.isdigit() and _is_lampp_pid(int(p_str), service_name):
                            lampp_running = True
                            break
            except Exception:
                pass
            if lampp_running:
                break

    # Capa 3: Sondeo TCP del puerto local asociado
    port_open = False
    port = info.get("port")
    if port:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.6):
                port_open = True
        except Exception:
            port_open = False

    if lampp_running:
        return ("● Activo", False)
    elif port_open:
        # Puerto ocupado pero NO por XAMPP -> Conflicto detectado
        return ("⚠️ Conflicto", True)
    else:
        return ("○ Inactivo", False)

def _is_service_running(info):
    """Compatibilidad: Devuelve True solo si el servicio de XAMPP está activo."""
    status, _ = detect_service_status(info)
    return status == "● Activo"

def detect_project_framework(project_path):
    """Detecta la tecnología o framework principal de un proyecto en htdocs.
    Devuelve una tupla: (nombre_framework, badge_str, color_hex)
    """
    if not project_path or not os.path.isdir(project_path):
        return ("Desconocido", "", "#888888")

    try:
        entries = set(os.listdir(project_path))
    except Exception:
        return ("General", "📁 General", "#888888")

    if not entries:
        return ("Vacío", "📁 Vacío", "#888888")

    # 1. Laravel (artisan CLI)
    if "artisan" in entries:
        return ("Laravel", "⚡ Laravel", "#e0564c")

    # 2. WordPress (wp-config.php o carpetas/archivos wp-*)
    if any(wp in entries for wp in ("wp-config.php", "wp-content", "wp-load.php", "wp-includes")):
        return ("WordPress", "📰 WordPress", "#21759b")

    # 3. Next.js / Node.js
    if "package.json" in entries:
        if any(f in entries for f in ("next.config.js", "next.config.mjs", "next.config.ts", ".next")):
            return ("Next.js", "▲ Next.js", "#0070f3")
        return ("Node.js", "📦 Node.js", "#68a063")

    # 4. Django
    if "manage.py" in entries:
        return ("Django", "🐍 Django", "#0c4b33")

    # 5. Python (Flask / FastAPI / scripts)
    if any(py in entries for py in ("requirements.txt", "Pipfile", "pyproject.toml", "wsgi.py", "app.py")):
        return ("Python", "🐍 Python", "#3776ab")

    # 6. Composer
    if "composer.json" in entries:
        return ("Composer", "🐘 Composer", "#777bb4")

    # 7. PHP tradicional
    if "index.php" in entries or any(f.endswith(".php") for f in entries):
        return ("PHP", "🐘 PHP", "#777bb4")

    # 8. HTML/JS estático
    if "index.html" in entries or any(f.endswith((".html", ".htm")) for f in entries):
        return ("HTML", "🌐 HTML", "#e34f26")

    return ("General", "📁 General", "#888888")

class XamppGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("XAMPP Control Center")
        self.root.geometry("520x760")
        self.root.resizable(False, False)
        
        self._cached_php = None
        self._is_closing = False
        self._status_lock = threading.Lock()
        self.service_status_badges = {}
        self.service_buttons = {}
        self.service_labels = []
        
        self.prefs = self.load_prefs()
        self.current_theme = self.prefs.get("theme", "dark")
        self.current_editor = self.prefs.get("editor", "VS Code")
        self.refresh_interval = self.prefs.get("refresh_interval", 4000)
        self.autostart = self.prefs.get("autostart", False)
        self.hidden_services = self.prefs.get("hidden_services", ["ProFTPD"])
        
        self._sanitize_prefs()
        
        self.progress_var = tk.DoubleVar()
        self.is_running = False
        
        self._secure_files()
        
        self.setup_ui()
        self.apply_theme()
        self.center_window(520, 770)
        self.setup_shortcuts()
        self.check_xampp()
        if self.autostart and SERVICES:
            self.root.after(500, self.start_all_quiet)
        self.auto_refresh()
        self.log_window = None
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        write_log("=== APLICACIÓN INICIADA ===")
        self.root.mainloop()

    def center_window(self, width, height):
        """Centra la ventana principal en la pantalla del usuario."""
        try:
            self.root.update_idletasks()
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
            x = max(0, (screen_w - width) // 2)
            y = max(0, (screen_h - height) // 2)
            self.root.geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            self.root.geometry(f"{width}x{height}")

    def setup_shortcuts(self):
        """Configura atajos de teclado globales para mejorar la ergonomía."""
        self.root.bind("<F5>", lambda e: self.update_status())
        self.root.bind("<Control-r>", lambda e: self.update_status())
        self.root.bind("<Control-q>", lambda e: self.on_close())
        self.root.bind("<Control-w>", lambda e: self.on_close())
        self.root.bind("<Control-Shift-S>", lambda e: self.run_cmd("start"))
        self.root.bind("<Control-Shift-s>", lambda e: self.run_cmd("start"))
        self.root.bind("<Control-Shift-X>", lambda e: self.run_cmd("stop"))
        self.root.bind("<Control-Shift-x>", lambda e: self.run_cmd("stop"))
    
    def safe_after(self, delay, callback):
        """Ejecuta un callback en el hilo de Tkinter de forma segura si la UI sigue viva."""
        if not getattr(self, "_is_closing", False):
            try:
                if self.root.winfo_exists():
                    self.root.after(delay, callback)
            except (tk.TclError, RuntimeError):
                pass
    
    def on_close(self):
        """Limpieza ordenada al cerrar la aplicación."""
        self._is_closing = True
        try:
            if hasattr(self, "_refresh_after") and self._refresh_after:
                self.root.after_cancel(self._refresh_after)
        except Exception:
            pass
        write_log("=== APLICACIÓN CERRADA ===")
        try:
            self.root.destroy()
        except Exception:
            pass
    
    def load_prefs(self):
        try:
            with open(PREFS_PATH, "r") as f:
                return json.load(f)
        except Exception as e:
            write_log(f"Error cargando preferencias: {e}")
            return {}
    
    def save_prefs(self):
        prefs = {
            "theme": self.current_theme,
            "editor": self.current_editor,
            "refresh_interval": self.refresh_interval,
            "autostart": self.autostart,
            "hidden_services": self.hidden_services
        }
        with open(PREFS_PATH, "w") as f:
            json.dump(prefs, f, indent=2)
        try:
            os.chmod(PREFS_PATH, 0o600)
        except Exception as e:
            write_log(f"Error aplicando permisos a prefs: {e}")
    
    def _sanitize_prefs(self):
        """Valida y corrige los valores de preferencias cargados del disco
        para evitar fallos en runtime si el JSON está corrupto o tiene
        valores con tipos inesperados."""
        # Tema debe ser una clave válida
        if self.current_theme not in THEMES:
            self.current_theme = "dark"
        # Editor debe ser una clave conocida
        if self.current_editor not in EDITORS:
            self.current_editor = "VS Code"
        # Intervalo de refresco debe ser un entero positivo razonable
        try:
            interval = int(self.refresh_interval)
            if interval < 500:
                interval = 4000
            self.refresh_interval = interval
        except (TypeError, ValueError):
            self.refresh_interval = 4000
        # Autostart booleano
        if not isinstance(self.autostart, bool):
            self.autostart = bool(self.autostart)
        # hidden_services debe ser una lista de strings
        if not isinstance(self.hidden_services, list):
            self.hidden_services = []
        else:
            self.hidden_services = [
                h for h in self.hidden_services if isinstance(h, str)
            ]
        # Asegurar consistencia con los servicios realmente instalados
        self.hidden_services = [
            h for h in self.hidden_services if h in ALL_SERVICES
        ]
    
    def _secure_files(self):
        """Fija permisos seguros a los archivos de datos de la app."""
        for path in (LOG_PATH, PREFS_PATH):
            if os.path.exists(path):
                try:
                    os.chmod(path, 0o600)
                except Exception as e:
                    write_log(f"Error asegurando permisos de {path}: {e}")
    
    def setup_ui(self):
        # Barra de menú
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Menú Configuración
        config_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Configuración", menu=config_menu)
        
        # Submenú de Editor
        editor_menu = tk.Menu(config_menu, tearoff=0)
        config_menu.add_cascade(label="Editor predeterminado", menu=editor_menu)
        for name in EDITORS:
            editor_menu.add_command(label=name, command=lambda n=name: self.set_editor(n))
        
        # Submenú de Tema
        theme_menu = tk.Menu(config_menu, tearoff=0)
        config_menu.add_cascade(label="Tema", menu=theme_menu)
        theme_menu.add_command(label="Oscuro", command=lambda: self.set_theme("dark"))
        theme_menu.add_command(label="Claro", command=lambda: self.set_theme("light"))
        
        # Intervalo de actualización
        refresh_menu = tk.Menu(config_menu, tearoff=0)
        config_menu.add_cascade(label="Intervalo de actualización", menu=refresh_menu)
        refresh_menu.add_command(label="2 segundos", command=lambda: self.set_refresh(2000))
        refresh_menu.add_command(label="4 segundos (default)", command=lambda: self.set_refresh(4000))
        refresh_menu.add_command(label="8 segundos", command=lambda: self.set_refresh(8000))
        refresh_menu.add_command(label="15 segundos", command=lambda: self.set_refresh(15000))
        
        config_menu.add_separator()
        self.autostart_var = tk.BooleanVar(value=self.autostart)
        config_menu.add_checkbutton(label="Iniciar servicios al abrir",
                                    variable=self.autostart_var,
                                    command=lambda: self.set_autostart(self.autostart_var.get()))
        
        config_menu.add_separator()
        services_menu = tk.Menu(config_menu, tearoff=0)
        config_menu.add_cascade(label="Servicios visibles", menu=services_menu)
        self.service_visibility_vars = {}
        for label in ALL_SERVICES:
            var = tk.BooleanVar(value=label not in self.hidden_services)
            self.service_visibility_vars[label] = var
            services_menu.add_checkbutton(label=label, variable=var,
                                          command=lambda l=label: self.toggle_service_visibility(l))
        
        config_menu.add_separator()
        config_menu.add_command(label="Abrir carpeta de logs", command=self.open_log_folder)
        config_menu.add_separator()
        config_menu.add_command(label="Administrador de Virtual Hosts...", command=self.show_vhosts_manager)
        config_menu.add_command(label="Generador de Certificados SSL (HTTPS)...", command=self.show_ssl_manager)
        config_menu.add_command(label="Puntos de Restauración (Snapshots)...", command=self.show_snapshots_manager)
        
        # Menú Base de Datos
        db_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Base de Datos", menu=db_menu)
        db_menu.add_command(label="Crear nueva Base de Datos...", command=self.create_database_dialog)
        db_menu.add_command(label="Consola MySQL (Terminal)", command=self.open_mysql_console)
        db_menu.add_separator()
        db_menu.add_command(label="Exportar respaldo (.sql)...", command=self.export_database_dump)
        db_menu.add_command(label="Importar respaldo (.sql)...", command=self.import_sql_file)
        db_menu.add_separator()
        db_menu.add_command(label="Abrir phpMyAdmin", command=self.open_phpmyadmin)

        # Menú Herramientas
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Herramientas", menu=tools_menu)
        tools_menu.add_command(label="Monitor de recursos en vivo (CPU/RAM)...", command=self.show_performance_monitor)
        tools_menu.add_command(label="Benchmark de rendimiento (ApacheBench)...", command=self.show_benchmark_dialog)
        tools_menu.add_command(label="Compartir proyecto en Internet (Túnel)...", command=self.show_tunnel_dialog)
        tools_menu.add_command(label="Monitor en vivo de logs (Live Tail)...", command=self.show_live_log_tail)
        tools_menu.add_command(label="Editor de reglas .htaccess...", command=self.show_htaccess_editor)
        tools_menu.add_separator()
        tools_menu.add_command(label="Entornos de PHP del sistema (CLI)...", command=self.show_php_environments_dialog)
        tools_menu.add_separator()
        tools_menu.add_command(label="Diagnosticar conflicto de puertos...", command=self.show_conflict_resolver)
        tools_menu.add_command(label="Extensiones de PHP activas...", command=self.show_php_extensions_dialog)
        tools_menu.add_separator()
        tools_menu.add_command(label="Limpiar logs del servidor...", command=self.purge_server_logs)
        tools_menu.add_command(label="Limpiar sesiones temporales...", command=self.clean_temp_sessions)
        tools_menu.add_separator()
        tools_menu.add_command(label="Estado del disco y espacio...", command=self.check_disk_health)
        tools_menu.add_command(label="Ajustes rápidos de PHP...", command=self.show_php_tweaks_dialog)
        tools_menu.add_separator()
        tools_menu.add_command(label="Instalar acceso directo en el sistema...", command=self.install_desktop_shortcut)

        # Menú Ayuda
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ayuda", menu=help_menu)
        help_menu.add_command(label="Acerca de", command=self.show_about)
        
        # Título
        self.title_label = tk.Label(self.root, text="XAMPP Control Center", 
                                     font=("Helvetica", 14, "bold"))
        self.title_label.pack(pady=8)
        
        # Barra de progreso
        self.progress_bar = ttk.Progressbar(self.root, variable=self.progress_var, 
                                            maximum=100, mode='indeterminate')
        self.progress_bar.pack(fill="x", padx=15, pady=2)
        self.progress_bar.pack_forget()
        
        # Frame principal con scroll
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Caja de Estado
        self.status_box = tk.Text(self.main_frame, height=4, font=("Monospace", 9, "bold"),
                                  relief="flat", padx=10, pady=6, cursor="arrow",
                                  highlightthickness=0)
        self.status_box.pack(fill="x", pady=4)
        self.status_box.tag_configure("title", font=("Monospace", 9, "bold"))
        self.status_box.tag_configure("label", font=("Monospace", 9, "bold"))
        self.status_box.tag_configure("active", font=("Monospace", 9, "bold"))
        self.status_box.tag_configure("inactive", font=("Monospace", 9, "bold"))
        self.status_box.tag_configure("conflict", font=("Monospace", 9, "bold"))
        self.status_box.tag_configure("php", font=("Monospace", 9, "normal"))
        self.status_box.configure(state="disabled")
        
        # Botón de actualización manual
        self.btn_frame_status = tk.Frame(self.main_frame)
        self.btn_frame_status.pack(fill="x", pady=2)
        self.btn_refresh = tk.Button(self.btn_frame_status, text="🔄 Actualizar Estado",
                                      font=("Helvetica", 9, "bold"), command=self.update_status)
        self.btn_refresh.pack(side="right", padx=2)
        
        # Servicios Individuales
        self.lbl_services = tk.Label(self.main_frame, text="Servicios Individuales",
                                      font=("Helvetica", 10, "bold"))
        self.lbl_services.pack(anchor="w", pady=(8, 4))
        
        self.frame_ind = tk.Frame(self.main_frame)
        self.frame_ind.pack(fill="x", pady=2)
        
        self.service_buttons = {}
        self.service_labels = []
        self.service_status_badges = {}
        self.rebuild_service_buttons()
        
        # Acciones Globales
        self.lbl_global = tk.Label(self.main_frame, text="Acciones Globales",
                                    font=("Helvetica", 10, "bold"))
        self.lbl_global.pack(anchor="w", pady=(10, 4))
        
        self.frame_servers = tk.Frame(self.main_frame)
        self.frame_servers.pack(fill="x", pady=2)
        
        self.btn_start_all = tk.Button(self.frame_servers, text="▶ Iniciar Todos",
                                         font=("Helvetica", 9, "bold"), width=12,
                                         command=lambda: self.run_cmd("start"))
        self.btn_start_all.grid(row=0, column=0, padx=2, pady=2)
        
        self.btn_stop_all = tk.Button(self.frame_servers, text="⏹ Detener Todos",
                                         font=("Helvetica", 9, "bold"), width=12,
                                         command=lambda: self.run_cmd("stop"))
        self.btn_stop_all.grid(row=0, column=1, padx=2, pady=2)
        
        self.btn_restart_all = tk.Button(self.frame_servers, text="🔄 Reiniciar Todos",
                                           font=("Helvetica", 9, "bold"), width=12,
                                           command=lambda: self.run_cmd("restart"))
        self.btn_restart_all.grid(row=0, column=2, padx=2, pady=2)
        
        # Panel Oficial
        self.lbl_official = tk.Label(self.main_frame, text="Panel Oficial XAMPP",
                                     font=("Helvetica", 10, "bold"))
        self.lbl_official.pack(anchor="w", pady=(10, 4))
        
        self.frame_official = tk.Frame(self.main_frame)
        self.frame_official.pack(fill="x", pady=2)
        
        self.btn_official = tk.Button(self.frame_official, text="🖥 Panel Oficial",
                                       font=("Helvetica", 9, "bold"), width=14,
                                       command=self.open_official_panel)
        self.btn_official.grid(row=0, column=0, padx=2, pady=2)
        
        # Mis Proyectos
        self.lbl_projects = tk.Label(self.main_frame, text="Mis Proyectos",
                                     font=("Helvetica", 10, "bold"))
        self.lbl_projects.pack(anchor="w", pady=(10, 4))
        
        self.frame_projects = tk.Frame(self.main_frame)
        self.frame_projects.pack(fill="x", pady=2)
        
        self.lbl_projects_sel = tk.Label(self.frame_projects, text="Proyecto:",
                                         font=("Helvetica", 9, "bold"), width=8, anchor="w")
        self.lbl_projects_sel.grid(row=0, column=0, padx=2, pady=2)
        self.project_var = tk.StringVar()
        self.project_combo = ttk.Combobox(self.frame_projects, textvariable=self.project_var,
                                          state="readonly", width=18)
        self.project_combo.grid(row=0, column=1, columnspan=2, padx=2, pady=2, sticky="w")
        self.project_combo.bind("<<ComboboxSelected>>", self.on_project_selected)
        
        self.btn_refresh_projects = tk.Button(self.frame_projects, text="🔄", width=3,
                                              font=("Helvetica", 9, "bold"),
                                              command=self.load_projects)
        self.btn_refresh_projects.grid(row=0, column=3, padx=2, pady=2)

        self.btn_new_project = tk.Button(self.frame_projects, text="➕", width=3,
                                         font=("Helvetica", 9, "bold"),
                                         command=self.new_project)
        self.btn_new_project.grid(row=0, column=4, padx=2, pady=2)

        self.lbl_framework = tk.Label(self.frame_projects, text="", font=("Helvetica", 8, "bold"))
        self.lbl_framework.grid(row=0, column=5, padx=4, pady=2, sticky="w")
        
        self.btn_open_editor = tk.Button(self.frame_projects, text="✏ Editor",
                                          width=8, font=("Helvetica", 8, "bold"),
                                          command=self.open_project_editor)
        self.btn_open_editor.grid(row=1, column=0, padx=2, pady=2)
        
        self.btn_open_terminal = tk.Button(self.frame_projects, text="💻 Terminal",
                                            width=9, font=("Helvetica", 8, "bold"),
                                            command=self.open_project_terminal)
        self.btn_open_terminal.grid(row=1, column=1, padx=2, pady=2)
        
        self.btn_open_browser = tk.Button(self.frame_projects, text="🌐 Navegador",
                                           width=10, font=("Helvetica", 8, "bold"),
                                           command=self.open_project_browser)
        self.btn_open_browser.grid(row=1, column=2, padx=2, pady=2)

        self.btn_open_folder = tk.Button(self.frame_projects, text="📁 Carpeta",
                                         width=8, font=("Helvetica", 8, "bold"),
                                         command=self.open_project_folder)
        self.btn_open_folder.grid(row=1, column=3, columnspan=2, padx=2, pady=2)
        
        self.load_projects()
        
        # Navegación y Proyectos
        self.lbl_nav = tk.Label(self.main_frame, text="Navegación y Proyectos",
                                 font=("Helvetica", 10, "bold"))
        self.lbl_nav.pack(anchor="w", pady=(10, 4))
        
        self.frame_nav = tk.Frame(self.main_frame)
        self.frame_nav.pack(fill="x", pady=2)
        
        self.btn_localhost = tk.Button(self.frame_nav, text="🌐 Localhost", width=11,
                                        command=self.open_localhost)
        self.btn_localhost.grid(row=0, column=0, padx=2, pady=2)
        
        self.btn_phpmyadmin = tk.Button(self.frame_nav, text="🗄 phpMyAdmin", width=11,
                                         command=self.open_phpmyadmin)
        self.btn_phpmyadmin.grid(row=0, column=1, padx=2, pady=2)
        
        self.btn_htdocs = tk.Button(self.frame_nav, text="📁 Ver htdocs", width=11,
                                     command=self.open_folder)
        self.btn_htdocs.grid(row=0, column=2, padx=2, pady=2)
        
        # Configuraciones Rápidas
        self.lbl_config = tk.Label(self.main_frame, text="Configuraciones Rápidas",
                                    font=("Helvetica", 10, "bold"))
        self.lbl_config.pack(anchor="w", pady=(10, 4))
        
        self.frame_cfg = tk.Frame(self.main_frame)
        self.frame_cfg.pack(fill="x", pady=2)
        
        self.btn_phpini = tk.Button(self.frame_cfg, text="⚙ php.ini", width=11,
                                     command=lambda: self.open_file("/opt/lampp/etc/php.ini"))
        self.btn_phpini.grid(row=0, column=0, padx=2, pady=2)
        
        self.btn_httpd = tk.Button(self.frame_cfg, text="⚙ httpd.conf", width=11,
                                    command=lambda: self.open_file("/opt/lampp/etc/httpd.conf"))
        self.btn_httpd.grid(row=0, column=1, padx=2, pady=2)
        
        self.btn_myconf = tk.Button(self.frame_cfg, text="⚙ my.cnf", width=11,
                                     command=lambda: self.open_file("/opt/lampp/etc/my.cnf"))
        self.btn_myconf.grid(row=0, column=2, padx=2, pady=2)
        
        # Registros / Logs
        self.lbl_logs = tk.Label(self.main_frame, text="Registros / Logs",
                                  font=("Helvetica", 10, "bold"))
        self.lbl_logs.pack(anchor="w", pady=(10, 4))
        
        self.frame_logs = tk.Frame(self.main_frame)
        self.frame_logs.pack(fill="x", pady=2)
        
        self.btn_errorlog = tk.Button(self.frame_logs, text="📜 Error Log", width=11,
                                       command=lambda: self.open_file("/opt/lampp/logs/error_log"))
        self.btn_errorlog.grid(row=0, column=0, padx=2, pady=2)
        
        self.btn_phperrorlog = tk.Button(self.frame_logs, text="📜 PHP Error Log", width=11,
                                          command=lambda: self.open_file("/opt/lampp/logs/php_error_log"))
        self.btn_phperrorlog.grid(row=0, column=1, padx=2, pady=2)
        
        self.btn_applog = tk.Button(self.frame_logs, text="📝 Log de la App", width=11,
                                     command=self.show_log_window)
        self.btn_applog.grid(row=0, column=2, padx=2, pady=2)
        
        self._ui_initialized = True
    
    def apply_theme(self):
        t = THEMES[self.current_theme]
        
        self.root.configure(bg=t["bg"])
        if hasattr(self, "title_label"):
            self.title_label.configure(bg=t["bg"], fg=t["fg"])
        
        if hasattr(self, "main_frame"):
            self.main_frame.configure(bg=t["bg"])
        if hasattr(self, "btn_frame_status"):
            self.btn_frame_status.configure(bg=t["bg"])
        
        if hasattr(self, "status_box"):
            self.status_box.configure(bg=t["bg_secondary"], fg=t["fg"])
            self.status_box.tag_configure("title", foreground=t["fg_label"])
            self.status_box.tag_configure("label", foreground=t["fg"])
            self.status_box.tag_configure("active", foreground=t["fg_active"])
            self.status_box.tag_configure("inactive", foreground=t["fg_inactive"])
            self.status_box.tag_configure("php", foreground=t["fg_label"])
            self.status_box.tag_configure("conflict", foreground=t.get("fg_conflict", "#f39c12"))
        
        if hasattr(self, "btn_refresh"):
            self.btn_refresh.configure(bg=t["bg_button"], fg=t["fg"])
        
        for lbl_name in ("lbl_services", "lbl_global", "lbl_official", "lbl_projects", "lbl_nav", "lbl_config", "lbl_logs"):
            if hasattr(self, lbl_name):
                getattr(self, lbl_name).configure(bg=t["bg"], fg=t["fg_label"])
        
        for frame_name in ("frame_ind", "frame_servers", "frame_official", "frame_projects", "frame_nav", "frame_cfg", "frame_logs"):
            if hasattr(self, frame_name):
                getattr(self, frame_name).configure(bg=t["bg"])
        
        if hasattr(self, "service_labels"):
            for lbl in self.service_labels:
                lbl.configure(bg=t["bg"])
                if not lbl.cget("text").startswith("No hay"):
                    lbl.configure(fg=t["fg"])
        
        for badge in getattr(self, "service_status_badges", {}).values():
            badge.configure(bg=t["bg"])
        
        if hasattr(self, "_last_statuses"):
            self._update_service_buttons(self._last_statuses)
        else:
            self._update_service_buttons({})
        
        for btn_name in ("btn_official", "btn_refresh_projects", "btn_new_project", "btn_open_editor", "btn_open_terminal", "btn_open_browser", "btn_open_folder", "btn_localhost", "btn_phpmyadmin", "btn_htdocs"):
            if hasattr(self, btn_name):
                getattr(self, btn_name).configure(bg=t["bg_button"], fg=t["fg"])
                
        if hasattr(self, "lbl_projects_sel"):
            self.lbl_projects_sel.configure(bg=t["bg"], fg=t["fg"])
        if hasattr(self, "lbl_framework"):
            self.lbl_framework.configure(bg=t["bg"])
        
        for cfg_btn in ("btn_phpini", "btn_httpd", "btn_myconf", "btn_errorlog", "btn_phperrorlog"):
            if hasattr(self, cfg_btn):
                getattr(self, cfg_btn).configure(bg=t["bg_button_config"], fg=t["fg"])
                
        if hasattr(self, "btn_applog"):
            self.btn_applog.configure(bg=t["bg_button_log"], fg="white")
    
    def set_theme(self, theme):
        self.current_theme = theme
        self.apply_theme()
        self.save_prefs()
        write_log(f"Tema cambiado a: {theme}")
    
    def set_editor(self, editor):
        if not self.is_editor_installed(editor):
            cmd = EDITORS.get(editor, "")
            write_log(f"Editor no instalado, no se cambia: {editor}")
            messagebox.showerror("Editor no encontrado",
                                 f"'{editor}' no está instalado.\n"
                                 f"Comando esperado: {cmd}")
            return
        self.current_editor = editor
        self.save_prefs()
        write_log(f"Editor cambiado a: {editor}")
        self.send_notification(f"Editor cambiado a {editor}")
    
    def is_editor_installed(self, editor):
        """Comprueba si el binario del editor está disponible en el sistema."""
        cmd = EDITORS.get(editor, "")
        if not cmd or cmd in ("nano", "vi"):
            return True
        return shutil.which(cmd) is not None
    
    def set_refresh(self, interval):
        self.refresh_interval = interval
        self.save_prefs()
        write_log(f"Intervalo de actualización: {interval}ms")
        self.send_notification(f"Actualización cada {interval//1000} segundos")
    
    def set_autostart(self, value):
        self.autostart = bool(value)
        self.save_prefs()
        write_log(f"Autostart de servicios: {'activado' if self.autostart else 'desactivado'}")
        self.send_notification("Autostart " + ("activado" if self.autostart else "desactivado"))
    
    def toggle_service_visibility(self, label):
        if label in self.hidden_services:
            self.hidden_services.remove(label)
        else:
            self.hidden_services.append(label)
        self.save_prefs()
        self.rebuild_service_buttons()
        write_log(f"Servicio {label}: {'visible' if label not in self.hidden_services else 'oculto'}")
    
    def rebuild_service_buttons(self):
        """Reconstruye los botones y badges de servicios según visibilidad."""
        for widget in self.frame_ind.winfo_children():
            widget.destroy()
        
        self.service_buttons = {}
        self.service_labels = []
        self.service_status_badges = {}
        
        visible = {k: v for k, v in SERVICES.items() if k not in self.hidden_services}
        
        if not visible:
            info_lbl = tk.Label(self.frame_ind, text="No hay servicios instalados o visibles",
                              font=("Helvetica", 9), fg="#dc3545", width=35, anchor="w")
            info_lbl.grid(row=0, column=0, columnspan=5, padx=2, pady=4)
            self.service_labels.append(info_lbl)
            return
        
        row = 0
        for name, info in visible.items():
            service = info["name"]
            self.service_buttons[service] = {}
            
            lbl = tk.Label(self.frame_ind, text=f"{name}:", 
                          font=("Helvetica", 9, "bold"), width=8, anchor="w")
            lbl.grid(row=row, column=0, padx=2, pady=2)
            self.service_labels.append(lbl)
            
            badge = tk.Label(self.frame_ind, text="○ Inactivo",
                             font=("Monospace", 9, "bold"), width=10, anchor="w")
            badge.grid(row=row, column=1, padx=2, pady=2)
            self.service_status_badges[service] = badge
            
            btn_start = tk.Button(self.frame_ind, text="▶ Iniciar",
                                  font=("Helvetica", 8, "bold"), width=8,
                                  command=lambda s=service: self.run_service("start", s))
            btn_start.grid(row=row, column=2, padx=2, pady=2)
            self.service_buttons[service]["start"] = btn_start
            
            btn_stop = tk.Button(self.frame_ind, text="⏹ Detener",
                                 font=("Helvetica", 8, "bold"), width=8,
                                 command=lambda s=service: self.run_service("stop", s))
            btn_stop.grid(row=row, column=3, padx=2, pady=2)
            self.service_buttons[service]["stop"] = btn_stop
            
            btn_restart = tk.Button(self.frame_ind, text="🔄 Reiniciar",
                                    font=("Helvetica", 8, "bold"), width=8,
                                    command=lambda s=service: self.run_service("restart", s))
            btn_restart.grid(row=row, column=4, padx=2, pady=2)
            self.service_buttons[service]["restart"] = btn_restart
            
            row += 1
        
        if getattr(self, "_ui_initialized", False):
            self.apply_theme()
        else:
            t = THEMES[self.current_theme]
            for lbl in self.service_labels:
                lbl.configure(bg=t["bg"])
                if not lbl.cget("text").startswith("No hay"):
                    lbl.configure(fg=t["fg"])
            for badge in self.service_status_badges.values():
                badge.configure(bg=t["bg"], fg=t["fg_inactive"])
            for btns in self.service_buttons.values():
                if "start" in btns:
                    btns["start"].configure(bg=t["btn_start"], fg="white")
                if "stop" in btns:
                    btns["stop"].configure(bg=t["btn_disabled_bg"], fg=t["btn_disabled_fg"], state="disabled")
                if "restart" in btns:
                    btns["restart"].configure(bg=t["btn_disabled_bg"], fg=t["btn_disabled_fg"], state="disabled")
        if hasattr(self, "_last_statuses"):
            self._update_service_buttons(self._last_statuses)
    
    def check_xampp(self):
        if not os.path.exists("/opt/lampp/lampp"):
            messagebox.showwarning("XAMPP no encontrado",
                                   "No se detectó XAMPP en /opt/lampp/lampp\n"
                                   "La aplicación puede no funcionar correctamente.")
            write_log("ADVERTENCIA: XAMPP no encontrado en /opt/lampp/lampp")
    
    def send_notification(self, message):
        try:
            subprocess.run(["notify-send", "XAMPP Control Center", message],
                          capture_output=True, timeout=2)
        except Exception as e:
            write_log(f"Error en notificación: {e}")
    
    def show_progress(self):
        self.progress_bar.pack(fill="x", padx=15, pady=2)
        self.progress_bar.start(15)
        self.is_running = True
    
    def hide_progress(self):
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self.is_running = False
        if hasattr(self, "_last_statuses"):
            self._update_service_buttons(self._last_statuses)
        else:
            self.update_status()
    
    def _set_buttons_state(self, state):
        """Habilita o deshabilita los botones de control durante una operación."""
        if hasattr(self, "service_buttons"):
            for btns in self.service_buttons.values():
                for btn in btns.values():
                    btn.configure(state=state)
        for btn_name in ("btn_start_all", "btn_stop_all", "btn_restart_all", "btn_refresh"):
            if hasattr(self, btn_name):
                getattr(self, btn_name).configure(state=state)
    
    def run_service(self, action, service):
        if self.is_running:
            return
        
        # Whitelist estricta para evitar inyección de comandos
        if action not in ("start", "stop", "restart"):
            write_log(f"Acción no permitida para servicio: {action}")
            return
        
        # Buscar metadata del servicio
        service_info = None
        for info in SERVICES.values():
            if info["name"] == service:
                service_info = info
                break
        
        if not service_info:
            write_log(f"Servicio no permitido: {service}")
            return
        
        cmd = service_info.get("cmd", service_info["name"])
        write_log(f"Ejecutando servicio individual: {action} {service} (cmd: {cmd})")
        self.show_progress()
        self._set_buttons_state("disabled")
        
        def execute():
            # Sin shell: lista de argumentos directa, previene inyección
            try:
                res = subprocess.run(
                    ["pkexec", "/opt/lampp/lampp", f"{action}{cmd}"],
                    capture_output=True, text=True, check=True, timeout=30)
                write_log(f"Salida: {res.stdout.strip()}")
                self.safe_after(0, self.update_status)
                self.safe_after(0, lambda: self.send_notification(f"{service} {action} completado"))
            except subprocess.TimeoutExpired:
                write_log(f"TIMEOUT al ejecutar {action} {service}")
                self.safe_after(0, lambda: messagebox.showerror("Timeout",
                    f"La operación {action} en {service} tardó demasiado."))
            except subprocess.CalledProcessError as e:
                write_log(f"ERROR al ejecutar {action} {service}:\nSTDOUT: {e.stdout}\nSTDERR: {e.stderr}")
                self.safe_after(0, lambda: messagebox.showerror("Error",
                    f"No se pudo ejecutar {action} en {service}."))
            finally:
                self.safe_after(0, self.hide_progress)
        
        threading.Thread(target=execute, daemon=True).start()
    
    def run_cmd(self, action):
        if self.is_running:
            return
        
        # Whitelist estricta
        if action not in ("start", "stop", "restart"):
            write_log(f"Acción global no permitida: {action}")
            return
        
        write_log(f"Ejecutando acción global: {action}")
        self.show_progress()
        self._set_buttons_state("disabled")
        
        visible_info = [info for label, info in SERVICES.items() if label not in self.hidden_services]
        all_services_visible = (len(visible_info) == len(SERVICES)) and len(SERVICES) > 0
        
        def execute():
            if not visible_info:
                self.safe_after(0, lambda: messagebox.showwarning("Sin servicios",
                    "No hay servicios instalados para operar."))
                self.safe_after(0, self.hide_progress)
                return
            
            try:
                if all_services_visible:
                    # Invocación atómica oficial de XAMPP (una sola autenticación polkit)
                    subprocess.run(
                        ["pkexec", "/opt/lampp/lampp", action],
                        capture_output=True, text=True, check=True, timeout=60)
                else:
                    for info in visible_info:
                        cmd = info.get("cmd", info["name"])
                        subprocess.run(
                            ["pkexec", "/opt/lampp/lampp", f"{action}{cmd}"],
                            capture_output=True, text=True, check=True, timeout=60)
                
                write_log(f"Acción global {action} completada")
                self.safe_after(0, self.update_status)
                self.safe_after(0, lambda: self.send_notification(f"Acción global {action} completada"))
            except subprocess.TimeoutExpired:
                write_log(f"TIMEOUT en acción global {action}")
                self.safe_after(0, lambda: messagebox.showerror("Timeout",
                    f"La operación global {action} tardó demasiado."))
            except subprocess.CalledProcessError as e:
                write_log(f"ERROR global:\nSTDOUT: {e.stdout}\nSTDERR: {e.stderr}")
                self.safe_after(0, lambda: messagebox.showerror("Error",
                    f"No se pudo ejecutar: {action}"))
            finally:
                self.safe_after(0, self.hide_progress)
        
        threading.Thread(target=execute, daemon=True).start()
    
    def start_all_quiet(self):
        """Inicia todos los servicios visibles sin diálogos ni barra de progreso (autostart)."""
        visible_info = [info for label, info in SERVICES.items() if label not in self.hidden_services]
        if not visible_info:
            return
        all_services_visible = (len(visible_info) == len(SERVICES)) and len(SERVICES) > 0
        write_log("Autostart: iniciando servicios")
        
        def execute():
            try:
                if all_services_visible:
                    subprocess.run(
                        ["pkexec", "/opt/lampp/lampp", "start"],
                        capture_output=True, text=True, check=True, timeout=60)
                else:
                    for info in visible_info:
                        cmd = info.get("cmd", info["name"])
                        subprocess.run(
                            ["pkexec", "/opt/lampp/lampp", f"start{cmd}"],
                            capture_output=True, text=True, check=True, timeout=60)
                write_log("Autostart: servicios iniciados")
                self.safe_after(0, self.update_status)
                self.safe_after(0, lambda: self.send_notification("Servicios iniciados (autostart)"))
            except Exception as e:
                write_log(f"AUTOSTART ERROR: {e}")
        
        threading.Thread(target=execute, daemon=True).start()

    def update_status(self):
        """Lanza la comprobación de estado en un hilo para no bloquear la UI."""
        if self.status_thread_alive() or getattr(self, "_is_closing", False):
            return
        threading.Thread(target=self._check_status_worker, daemon=True).start()
    
    def status_thread_alive(self):
        t = getattr(self, "_status_thread", None)
        return t is not None and t.is_alive()
    
    def _check_status_worker(self):
        """Ejecuta las comprobaciones de estado fuera del hilo de la UI."""
        if getattr(self, "_is_closing", False):
            return
        self._status_thread = threading.current_thread()
        with self._status_lock:
            try:
                statuses = {}
                for label, info in SERVICES.items():
                    if label in self.hidden_services:
                        continue
                    status_str, _ = detect_service_status(info)
                    statuses[label] = status_str
                
                php_version = getattr(self, "_cached_php", None)
                if not php_version:
                    try:
                        res = subprocess.run(["/opt/lampp/bin/php", "-v"], capture_output=True, text=True, timeout=3)
                        first_line = res.stdout.strip().splitlines()[0] if res.stdout.strip() else ""
                        if "PHP" in first_line:
                            php_version = first_line.split()[1]
                            self._cached_php = php_version
                    except Exception:
                        php_version = ""
                
                self._last_statuses = statuses
                self._last_php = php_version
                self.safe_after(0, self._apply_status_ui)
            except Exception as e:
                write_log(f"Error verificando estado: {str(e)}")
    
    def _apply_status_ui(self):
        """Aplica el estado calculado a la UI (se ejecuta en el hilo principal)."""
        if getattr(self, "_is_closing", False):
            return
        statuses = getattr(self, "_last_statuses", {})
        php_version = getattr(self, "_last_php", "")
        
        self.status_box.configure(state="normal")
        self.status_box.delete("1.0", tk.END)
        self.status_box.insert(tk.END, "Estado de Servicios:\n", "title")
        for label, status in statuses.items():
            self.status_box.insert(tk.END, f"  {label}: ", "label")
            if status == "● Activo":
                tag = "active"
            elif "Conflicto" in status:
                tag = "conflict"
            else:
                tag = "inactive"
            self.status_box.insert(tk.END, f"{status}\n", tag)
        if php_version:
            self.status_box.insert(tk.END, f"  PHP {php_version}\n", "php")
        has_conflicts = any("Conflicto" in s for s in statuses.values())
        if has_conflicts:
            self.status_box.insert(tk.END, "  ⚠️ Puerto ocupado por servicio del sistema\n", "conflict")
        self.status_box.configure(state="disabled")
        
        self._update_service_buttons(statuses)
        
        state_key = "|".join(statuses.values())
        if not hasattr(self, "_last_state") or self._last_state != state_key:
            self._last_state = state_key
            resumen = ", ".join(f"{label.split()[0]}[{'ON' if s=='● Activo' else ('CONFLICT' if 'Conflicto' in s else 'OFF')}]" for label, s in statuses.items())
            write_log(f"Estado: {resumen} | {php_version}")
    
    def _update_service_buttons(self, statuses):
        """Actualiza el texto, habilitado y colores de los botones y badges según el estado."""
        if not hasattr(self, "service_buttons") or getattr(self, "_is_closing", False):
            return
        
        t = THEMES[self.current_theme]
        service_statuses = {info["name"]: statuses.get(label, "○ Inactivo")
                            for label, info in ALL_SERVICES.items()}
        
        for service, btns in self.service_buttons.items():
            st = service_statuses.get(service, "○ Inactivo")
            active = (st == "● Activo")
            conflict = ("Conflicto" in st)
            
            # Actualizar badge en la fila del servicio
            badge = self.service_status_badges.get(service)
            if badge:
                badge_fg = t["fg_active"] if active else (t.get("fg_conflict", "#f39c12") if conflict else t["fg_inactive"])
                badge.configure(
                    text=st,
                    fg=badge_fg,
                    bg=t["bg"]
                )
            
            if self.is_running:
                if "start" in btns:
                    btns["start"].configure(state="disabled", bg=t["btn_disabled_bg"], fg=t["btn_disabled_fg"])
                if "stop" in btns:
                    btns["stop"].configure(state="disabled", bg=t["btn_disabled_bg"], fg=t["btn_disabled_fg"])
                if "restart" in btns:
                    btns["restart"].configure(state="disabled", bg=t["btn_disabled_bg"], fg=t["btn_disabled_fg"])
            else:
                if "start" in btns:
                    if active:
                        btns["start"].configure(state="disabled", text="▶ Iniciar",
                                                bg=t["btn_disabled_bg"], fg=t["btn_disabled_fg"])
                    else:
                        btns["start"].configure(state="normal", text="▶ Iniciar",
                                                bg=t["btn_start"], fg="white")
                if "stop" in btns:
                    if active:
                        btns["stop"].configure(state="normal", text="⏹ Detener",
                                               bg=t["btn_stop"], fg="white")
                    else:
                        btns["stop"].configure(state="disabled", text="⏹ Detener",
                                               bg=t["btn_disabled_bg"], fg=t["btn_disabled_fg"])
                if "restart" in btns:
                    if active:
                        btns["restart"].configure(state="normal", text="🔄 Reiniciar",
                                                  bg=t["btn_restart"], fg="white")
                    else:
                        btns["restart"].configure(state="disabled", text="🔄 Reiniciar",
                                                  bg=t["btn_disabled_bg"], fg=t["btn_disabled_fg"])
        
        # Actualizar botones globales
        visible_services = [info["name"] for label, info in SERVICES.items() if label not in self.hidden_services]
        num_active = sum(1 for s in visible_services if service_statuses.get(s) == "● Activo")
        num_total = len(visible_services)
        all_active = (num_active == num_total) if num_total > 0 else False
        none_active = (num_active == 0)
        
        if hasattr(self, "btn_start_all"):
            if self.is_running or all_active or num_total == 0:
                self.btn_start_all.configure(state="disabled", bg=t["btn_disabled_bg"], fg=t["btn_disabled_fg"])
            else:
                self.btn_start_all.configure(state="normal", bg=t["btn_start_global"], fg="white")
                
        if hasattr(self, "btn_stop_all"):
            if self.is_running or none_active or num_total == 0:
                self.btn_stop_all.configure(state="disabled", bg=t["btn_disabled_bg"], fg=t["btn_disabled_fg"])
            else:
                self.btn_stop_all.configure(state="normal", bg=t["btn_stop_global"], fg="white")
                
        if hasattr(self, "btn_restart_all"):
            if self.is_running or none_active or num_total == 0:
                self.btn_restart_all.configure(state="disabled", bg=t["btn_disabled_bg"], fg=t["btn_disabled_fg"])
            else:
                self.btn_restart_all.configure(state="normal", bg=t["btn_restart_global"], fg="white")
    
    def auto_refresh(self):
        if getattr(self, "_is_closing", False):
            return
        try:
            self._refresh_after = self.root.after(self.refresh_interval, self.auto_refresh)
        except tk.TclError:
            return
        self.update_status()
    
    def open_folder(self):
        write_log("Abriendo htdocs")
        subprocess.Popen(["xdg-open", "/opt/lampp/htdocs"])
    
    def open_file(self, path):
        write_log(f"Abriendo archivo: {path} con {self.current_editor}")
        editor_cmd = EDITORS.get(self.current_editor, "xdg-open")
        
        # Validar que el editor está instalado antes de lanzarlo
        if not shutil.which(editor_cmd):
            write_log(f"Editor no encontrado: {editor_cmd}")
            messagebox.showerror("Editor no encontrado",
                                 f"El editor '{self.current_editor}' no está instalado.\n"
                                 f"Comando esperado: {editor_cmd}\n\n"
                                 "Cambia el editor en Configuración para continuar.")
            return
        
        # Advertencia de permisos si el archivo pertenece a root y el usuario no puede escribirlo
        if os.path.exists(path) and not os.access(path, os.W_OK):
            write_log(f"Aviso: El archivo {path} requiere permisos de superusuario para guardar cambios.")
        
        if editor_cmd in ["nano", "vi"]:
            terminal = self.find_terminal()
            if terminal:
                subprocess.Popen([terminal, "-e", editor_cmd, path])
            else:
                subprocess.Popen(["xdg-open", path])
        else:
            subprocess.Popen([editor_cmd, path])
    
    def find_terminal(self):
        """Busca emuladores de terminal instalados sin crear procesos de shell."""
        terminals = [
            "x-terminal-emulator", "gnome-terminal", "konsole",
            "xfce4-terminal", "mate-terminal", "alacritty", "kitty",
            "tilix", "terminator", "lxterminal", "xterm"
        ]
        for term in terminals:
            if shutil.which(term):
                return term
        return None
    
    def open_log_folder(self):
        log_dir = os.path.dirname(LOG_PATH)
        write_log(f"Abriendo carpeta de logs: {log_dir}")
        subprocess.Popen(["xdg-open", log_dir])
    
    def _read_all_logs(self):
        """Lee el log actual y los rotados (de más antiguo a más nuevo)."""
        parts = []
        for i in range(LOG_MAX_FILES, 0, -1):
            path = f"{LOG_PATH}.{i}"
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        parts.append(f.read())
                except Exception as e:
                    write_log(f"Error leyendo log rotado {path}: {e}")
        if os.path.exists(LOG_PATH):
            try:
                with open(LOG_PATH, "r", encoding="utf-8") as f:
                    parts.append(f.read())
            except Exception as e:
                write_log(f"Error leyendo log {LOG_PATH}: {e}")
        return "\n".join(parts)

    def show_log_window(self):
        if self.log_window:
            try:
                if self.log_window.winfo_exists():
                    self.log_window.lift()
                    return
            except Exception:
                self.log_window = None
        
        t = THEMES[self.current_theme]
        self.log_window = tk.Toplevel(self.root)
        self.log_window.title("Log de la Aplicación")
        self.log_window.geometry("640x480")
        self.log_window.configure(bg=t["bg"])
        
        # Barra de búsqueda
        search_frame = tk.Frame(self.log_window, bg=t["bg"])
        search_frame.pack(fill="x", padx=5, pady=5)
        
        tk.Label(search_frame, text="Buscar:", bg=t["bg"], fg=t["fg"],
                 font=("Helvetica", 9, "bold")).pack(side="left", padx=2)
        
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(search_frame, textvariable=self.search_var,
                                     width=30, bg=t["bg_secondary"], fg=t["fg"],
                                     insertbackground=t["fg"])
        self.search_entry.pack(side="left", padx=2)
        self.search_entry.bind("<Return>", lambda e: self.search_log(self.text_area))
        
        tk.Button(search_frame, text="🔍 Buscar", bg=t["bg_button"], fg=t["fg"],
                  command=lambda: self.search_log(self.text_area)).pack(side="left", padx=2)
        
        self.text_area = scrolledtext.ScrolledText(self.log_window, wrap=tk.WORD,
                                                   font=("Monospace", 9),
                                                   bg=t["bg_secondary"], fg=t["fg"],
                                                   insertbackground=t["fg"])
        self.text_area.pack(fill="both", expand=True, padx=5)
        
        content = self._read_all_logs()
        if content.strip():
            self.text_area.insert(tk.END, content)
            self.text_area.see(tk.END)
        else:
            self.text_area.insert(tk.END, "No hay registros disponibles.")
        
        self.text_area.configure(state="disabled")
        
        btn_frame = tk.Frame(self.log_window, bg=t["bg"])
        btn_frame.pack(fill="x", padx=5, pady=5)
        
        tk.Button(btn_frame, text="🔄 Actualizar", bg=t["bg_button"], fg=t["fg"],
                  command=lambda: self.refresh_log(self.text_area)).pack(side="left", padx=2)
        tk.Button(btn_frame, text="🗑 Limpiar", bg=t["btn_stop"], fg="white",
                  command=lambda: self.clear_log(self.text_area)).pack(side="left", padx=2)
        tk.Button(btn_frame, text="📋 Copiar", bg=t["bg_button"], fg=t["fg"],
                  command=lambda: self.copy_log(self.text_area)).pack(side="left", padx=2)
        tk.Button(btn_frame, text="⬇ Exportar", bg=t["bg_button_config"], fg=t["fg"],
                  command=self.export_log).pack(side="left", padx=2)
    
    def refresh_log(self, text_area):
        text_area.configure(state="normal")
        text_area.delete(1.0, tk.END)
        content = self._read_all_logs()
        if content.strip():
            text_area.insert(tk.END, content)
            text_area.see(tk.END)
        else:
            text_area.insert(tk.END, "No hay registros disponibles.")
        text_area.configure(state="disabled")
    
    def search_log(self, text_area):
        query = self.search_var.get().strip().lower()
        if not query:
            return
        text_area.configure(state="normal")
        text_area.tag_remove("match", "1.0", tk.END)
        start = "1.0"
        count = 0
        while True:
            idx = text_area.search(query, start, stopindex=tk.END, nocase=True)
            if not idx:
                break
            end = f"{idx}+{len(query)}c"
            text_area.tag_add("match", idx, end)
            text_area.tag_config("match", background="#f39c12", foreground="#000000")
            start = end
            count += 1
        text_area.configure(state="disabled")
        self.send_notification(f"{count} coincidencia(s)")
    
    def clear_log(self, text_area):
        if messagebox.askyesno("Confirmar", "¿Limpiar todo el log?"):
            try:
                with open(LOG_PATH, "w") as f:
                    f.write("")
                text_area.configure(state="normal")
                text_area.delete(1.0, tk.END)
                text_area.insert(tk.END, "Log limpiado.")
                text_area.configure(state="disabled")
                write_log("Log limpiado por el usuario")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo limpiar: {e}")
    
    def export_log(self):
        from tkinter import filedialog
        content = self._read_all_logs()
        default_name = f"xampp-log-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
        file_path = filedialog.asksaveasfilename(
            title="Exportar log",
            initialfile=default_name,
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("Todos los archivos", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                self.send_notification(f"Log exportado a {os.path.basename(file_path)}")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo exportar: {e}")
    
    def copy_log(self, text_area):
        self.root.clipboard_clear()
        self.root.clipboard_append(text_area.get(1.0, tk.END))
        self.send_notification("Log copiado al portapapeles")
    
    def show_about(self):
        installed = ", ".join(SERVICES.keys()) if SERVICES else "ninguno"
        messagebox.showinfo("Acerca de",
                           "XAMPP Control Center v2.6\n\n"
                           "Suite gráfica avanzada para administrar XAMPP en Linux (Mint, Ubuntu, Debian).\n\n"
                           f"Servicios detectados: {installed}\n"
                           "Características v2.6:\n"
                           "• Benchmark de rendimiento y pruebas de carga con ApacheBench (ab)\n"
                           "• Compartir proyectos a Internet vía Túnel SSH seguro\n"
                           "• Monitor de logs en vivo (Live Tail) con coloreado sintáctico\n"
                           "• Editor visual y plantillas de reglas .htaccess\n"
                           "• Generador de Certificados SSL y soporte HTTPS local\n"
                           "• Monitor de Rendimiento en Tiempo Real (CPU, RAM y conexiones)\n"
                           "• Gestor de Snapshots y Puntos de Restauración con 1-clic Rollback\n"
                           "• Selector de Entornos PHP Multi-Versión y lanzador CLI\n"
                           "• Administrador de Virtual Hosts y resolución de conflictos de puertos")

    def _port_open(self, host, port, timeout=1.0):
        """Comprueba si un puerto responde en localhost."""
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except Exception:
            return False

    def on_project_selected(self, event=None):
        """Actualiza la insignia de tecnología del proyecto seleccionado."""
        name = self.project_var.get().strip() if hasattr(self, "project_var") else ""
        if not name:
            if hasattr(self, "lbl_framework"):
                self.lbl_framework.configure(text="")
            return
        path = os.path.join(HTDOCS_PATH, name)
        _, badge, color = detect_project_framework(path)
        if hasattr(self, "lbl_framework"):
            self.lbl_framework.configure(text=badge, fg=color)

    def load_projects(self):
        """Lista las carpetas (proyectos) del directorio htdocs en el Combobox."""
        projects = []
        system_folders = {"img", "webalizer"}
        try:
            if os.path.isdir(HTDOCS_PATH):
                for entry in os.scandir(HTDOCS_PATH):
                    if entry.is_dir() and not entry.name.startswith("."):
                        if entry.name.lower() not in system_folders:
                            projects.append(entry.name)
        except Exception as e:
            write_log(f"Error listando proyectos en {HTDOCS_PATH}: {e}")
            projects = []
        projects.sort(key=str.lower)
        self.projects = projects
        self.project_combo["values"] = projects
        current = self.project_var.get()
        if projects:
            if not current or current not in projects:
                self.project_var.set(projects[0])
        else:
            self.project_var.set("")
        self.on_project_selected()

    def new_project(self):
        """Crea una nueva carpeta de proyecto dentro de htdocs."""
        from tkinter import simpledialog
        name = simpledialog.askstring("Nuevo Proyecto", "Introduce el nombre del nuevo proyecto:", parent=self.root)
        if not name:
            return
        name = name.strip()
        # Validación de seguridad: evitar path traversal y nombres inválidos
        if not name or any(c in name for c in ('/', '\\', '..', ':', '*', '?', '"', '<', '>', '|')) or name.startswith('.'):
            messagebox.showerror("Nombre inválido", "El nombre del proyecto solo puede contener letras, números, guiones y subrayados.")
            return
        
        target_path = os.path.join(HTDOCS_PATH, name)
        if os.path.exists(target_path):
            messagebox.showwarning("Ya existe", f"Ya existe una carpeta o proyecto con el nombre '{name}'.")
            return
        
        try:
            os.makedirs(target_path, exist_ok=True)
            write_log(f"Nuevo proyecto creado: {target_path}")
            self.load_projects()
            self.project_var.set(name)
            self.on_project_selected()
            self.send_notification(f"Proyecto '{name}' creado con éxito")
        except PermissionError:
            write_log(f"Permiso denegado al crear proyecto en {target_path}")
            messagebox.showerror(
                "Permiso denegado",
                f"No tienes permisos para escribir en {HTDOCS_PATH}.\n\n"
                f"Ejecuta en tu terminal:\nsudo chown -R $USER:$USER {HTDOCS_PATH}\n"
                "para permitir a tu usuario crear proyectos sin restricciones."
            )
        except Exception as e:
            write_log(f"Error creando proyecto: {e}")
            messagebox.showerror("Error", f"No se pudo crear el proyecto:\n{e}")

    def open_project_folder(self):
        """Abre la carpeta del proyecto seleccionado en el explorador de archivos."""
        path = self.get_selected_project()
        if not path:
            return
        write_log(f"Abriendo carpeta del proyecto: {path}")
        subprocess.Popen(["xdg-open", path])
    
    def get_selected_project(self):
        name = self.project_var.get().strip()
        if not name:
            messagebox.showinfo("Sin proyecto", "Selecciona un proyecto primero.")
            return None
        path = os.path.join(HTDOCS_PATH, name)
        if not os.path.isdir(path):
            messagebox.showerror("No existe",
                                 f"El proyecto no existe:\n{path}")
            return None
        return path
    
    def open_project_editor(self):
        path = self.get_selected_project()
        if not path:
            return
        write_log(f"Abriendo proyecto en editor: {path}")
        self.open_file(path)
    
    def open_project_terminal(self):
        path = self.get_selected_project()
        if not path:
            return
        write_log(f"Abriendo terminal en: {path}")
        terminal = self.find_terminal()
        if not terminal:
            messagebox.showwarning("Sin terminal",
                                   "No se encontró un emulador de terminal.")
            return

        cmd = [terminal]
        if "konsole" in terminal:
            cmd.extend(["--workdir", path])
        elif terminal in ("gnome-terminal", "mate-terminal", "xfce4-terminal", "tilix", "terminator", "alacritty"):
            cmd.extend(["--working-directory", path])
        elif "kitty" in terminal:
            cmd.extend(["-d", path])
        
        try:
            subprocess.Popen(cmd, cwd=path)
        except Exception as e:
            write_log(f"Error lanzando terminal con argumentos específicos: {e}")
            try:
                subprocess.Popen([terminal], cwd=path)
            except Exception as e2:
                messagebox.showerror("Error", f"No se pudo abrir el terminal:\n{e2}")
    
    def open_project_browser(self):
        path = self.get_selected_project()
        if not path:
            return
        if not self._port_open("127.0.0.1", 80):
            messagebox.showwarning("Apache no está corriendo",
                                   "El puerto 80 no responde.\n"
                                   "Inicia Apache antes de abrir el proyecto.")
            return
        framework, _, _ = detect_project_framework(path)
        name = os.path.basename(path)
        if framework == "Laravel" and os.path.isdir(os.path.join(path, "public")):
            url = f"http://localhost/{quote(name)}/public"
        else:
            url = f"http://localhost/{quote(name)}"
        write_log(f"Abriendo proyecto en navegador: {url} (framework: {framework})")
        webbrowser.open(url)

    def open_localhost(self):
        if not self._port_open("127.0.0.1", 80):
            messagebox.showwarning("Apache no está corriendo",
                                   "El puerto 80 no responde.\n"
                                   "Inicia Apache antes de abrir Localhost.")
            return
        webbrowser.open("http://localhost")

    def open_phpmyadmin(self):
        if not self._port_open("127.0.0.1", 80):
            messagebox.showwarning("Apache no está corriendo",
                                   "El puerto 80 no responde.\n"
                                   "Inicia Apache antes de abrir phpMyAdmin.")
            return
        webbrowser.open("http://localhost/phpmyadmin")
    
    def open_official_panel(self):
        """Abre el panel oficial de XAMPP."""
        panel_paths = [
            "/opt/lampp/manager-linux-x64.run",
            "/opt/lampp/manager-linux-x32.run",
            "/opt/lampp/manager-linux.run"
        ]
        panel = None
        for path in panel_paths:
            if os.path.exists(path):
                panel = path
                break
        if not panel:
            write_log("Panel oficial no encontrado")
            messagebox.showwarning("Panel no encontrado",
                                   "No se encontró el panel oficial de XAMPP.\n"
                                   "Rutas buscadas:\n" + "\n".join(panel_paths))
            return
        
        write_log(f"Abriendo panel oficial: {panel}")
        display = os.environ.get("DISPLAY", ":0")
        xauth = os.environ.get("XAUTHORITY", os.path.expanduser("~/.Xauthority"))
        
        try:
            if os.geteuid() == 0:
                # Ya somos root
                subprocess.Popen([panel], env=os.environ.copy())
                return
            
            env = os.environ.copy()
            env["DISPLAY"] = display
            if xauth:
                env["XAUTHORITY"] = xauth
            
            # Ejecutar el panel como root vía pkexec propagando DISPLAY y el
            # Xauthority del usuario. Root puede leer el .Xauthority (ignora
            # permisos de lectura), así que NO es necesario abrir el display
            # con xhost (evita el riesgo de captura de X keylogging).
            # Se usa "pkexec env VAR=val prog" con argumentos listados (sin
            # shell), lo que elimina cualquier riesgo de inyección de comandos.
            args = ["pkexec", "env", f"DISPLAY={display}", panel]
            if xauth:
                args.insert(3, f"XAUTHORITY={xauth}")
            subprocess.Popen(args, env=env)
        except Exception as e:
            write_log(f"Error abriendo panel oficial: {e}")
            messagebox.showerror("Error", f"No se pudo abrir el panel oficial:\n{e}")

    # =========================================================================
    # Herramientas de Base de Datos (MySQL)
    # =========================================================================

    def _get_mysql_bin(self, binary="mysql"):
        """Retorna la ruta al binario de MySQL o mysqldump de XAMPP o del sistema."""
        xampp_bin = f"/opt/lampp/bin/{binary}"
        if os.path.isfile(xampp_bin) and os.access(xampp_bin, os.X_OK):
            return xampp_bin
        return shutil.which(binary) or xampp_bin

    def _list_mysql_databases(self):
        """Retorna lista de bases de datos de usuario en MySQL."""
        mysql_bin = self._get_mysql_bin("mysql")
        try:
            res = subprocess.run(
                [mysql_bin, "-u", "root", "-B", "-N", "-e", "SHOW DATABASES;"],
                capture_output=True, text=True, timeout=5
            )
            if res.returncode == 0:
                sys_dbs = {"information_schema", "performance_schema", "mysql", "sys"}
                dbs = [db.strip() for db in res.stdout.splitlines() if db.strip() and db.strip() not in sys_dbs]
                return dbs
        except Exception as e:
            write_log(f"Error listando bases de datos: {e}")
        return []

    def create_database_dialog(self):
        """Diálogo interactivo para crear una base de datos en MySQL."""
        if not self._port_open("127.0.0.1", 3306):
            messagebox.showwarning(
                "MySQL inactivo",
                "El servicio MySQL no está corriendo (puerto 3306 inactivo).\n"
                "Inicia MySQL antes de crear una base de datos."
            )
            return

        from tkinter import simpledialog
        db_name = simpledialog.askstring(
            "Crear Base de Datos",
            "Introduce el nombre de la nueva base de datos:",
            parent=self.root
        )
        if not db_name:
            return
        db_name = db_name.strip()
        
        # Validación de seguridad: identificador SQL alfanumérico y guiones bajos
        if not re.match(r'^[a-zA-Z0-9_]+$', db_name):
            messagebox.showerror(
                "Nombre inválido",
                "El nombre de la base de datos solo puede contener letras, números y guiones bajos (_)."
            )
            return

        mysql_bin = self._get_mysql_bin("mysql")
        sql = f"CREATE DATABASE `{db_name}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        try:
            res = subprocess.run(
                [mysql_bin, "-u", "root", "-e", sql],
                capture_output=True, text=True, timeout=10
            )
            if res.returncode == 0:
                write_log(f"Base de datos '{db_name}' creada exitosamente.")
                self.send_notification(f"Base de datos '{db_name}' creada.")
                messagebox.showinfo("Éxito", f"Base de datos '{db_name}' creada exitosamente en MySQL.")
            else:
                err = res.stderr.strip() or res.stdout.strip()
                write_log(f"Error al crear base de datos '{db_name}': {err}")
                if "database exists" in err.lower():
                    err_msg = f"La base de datos '{db_name}' ya existe en MySQL."
                elif "access denied" in err.lower():
                    err_msg = "Acceso denegado: el usuario root tiene contraseña o permisos restringidos."
                else:
                    err_msg = f"No se pudo crear la base de datos:\n{err}"
                messagebox.showerror("Error MySQL", err_msg)
        except Exception as e:
            write_log(f"Excepción al crear BD: {e}")
            messagebox.showerror("Error", f"Error ejecutando MySQL:\n{e}")

    def open_mysql_console(self):
        """Abre una consola interactiva de MySQL en el terminal del usuario."""
        if not self._port_open("127.0.0.1", 3306):
            messagebox.showwarning(
                "MySQL inactivo",
                "El servicio MySQL no está corriendo (puerto 3306 inactivo).\n"
                "Inicia MySQL antes de abrir la consola."
            )
            return

        terminal = self.find_terminal()
        if not terminal:
            messagebox.showwarning("Sin terminal", "No se encontró un emulador de terminal compatible.")
            return

        mysql_bin = self._get_mysql_bin("mysql")
        shell_cmd = f"echo '=== Consola MySQL XAMPP (root) ==='; '{mysql_bin}' -u root; exec bash"
        
        cmd = [terminal]
        if terminal in ("gnome-terminal", "mate-terminal", "xfce4-terminal", "tilix", "terminator"):
            cmd.extend(["--", "bash", "-c", shell_cmd])
        elif "konsole" in terminal or "alacritty" in terminal or "xterm" in terminal:
            cmd.extend(["-e", "bash", "-c", shell_cmd])
        elif "kitty" in terminal:
            cmd.extend(["bash", "-c", shell_cmd])
        else:
            cmd.extend(["-e", "bash", "-c", shell_cmd])

        try:
            write_log(f"Abriendo consola MySQL en {terminal}")
            subprocess.Popen(cmd)
        except Exception as e:
            write_log(f"Error abriendo consola MySQL: {e}")
            messagebox.showerror("Error", f"No se pudo abrir el terminal:\n{e}")

    def export_database_dump(self):
        """Exporta un respaldo (.sql) de una base de datos mediante mysqldump."""
        if not self._port_open("127.0.0.1", 3306):
            messagebox.showwarning("MySQL inactivo", "Inicia MySQL antes de exportar un respaldo.")
            return

        from tkinter import simpledialog, filedialog
        databases = self._list_mysql_databases()
        if databases:
            db_dialog = tk.Toplevel(self.root)
            db_dialog.title("Exportar Base de Datos")
            db_dialog.geometry("340x160")
            db_dialog.resizable(False, False)
            db_dialog.transient(self.root)
            db_dialog.grab_set()
            
            t = THEMES[self.current_theme]
            db_dialog.configure(bg=t["bg"])
            
            tk.Label(db_dialog, text="Selecciona la base de datos a exportar:",
                     bg=t["bg"], fg=t["fg"], font=("Helvetica", 9, "bold")).pack(pady=(15, 5))
            
            combo_var = tk.StringVar(value=databases[0])
            combo = ttk.Combobox(db_dialog, textvariable=combo_var, values=databases, state="readonly", width=25)
            combo.pack(pady=5)
            
            selected_db = [None]
            def on_confirm():
                selected_db[0] = combo_var.get().strip()
                db_dialog.destroy()
                
            tk.Button(db_dialog, text="Continuar", bg=t["btn_start"], fg="white",
                      font=("Helvetica", 9, "bold"), command=on_confirm).pack(pady=10)
            
            self.root.wait_window(db_dialog)
            target_db = selected_db[0]
        else:
            target_db = simpledialog.askstring("Exportar Base de Datos", "Nombre de la base de datos:", parent=self.root)
            
        if not target_db:
            return
            
        default_file = f"{target_db}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
        save_path = filedialog.asksaveasfilename(
            title=f"Guardar respaldo de '{target_db}'",
            initialfile=default_file,
            defaultextension=".sql",
            filetypes=[("Archivos SQL", "*.sql"), ("Todos los archivos", "*.*")]
        )
        if not save_path:
            return

        self.show_progress()
        self.send_notification(f"Exportando base de datos '{target_db}'...")
        write_log(f"Iniciando exportación de '{target_db}' a {save_path}")

        def run_export():
            dump_bin = self._get_mysql_bin("mysqldump")
            try:
                dump_cmd = [
                    dump_bin, "-u", "root",
                    "--single-transaction",
                    "--routines",
                    "--triggers",
                    "--default-character-set=utf8mb4",
                    target_db
                ]
                with open(save_path, "w", encoding="utf-8") as out_f:
                    res = subprocess.run(
                        dump_cmd,
                        stdout=out_f, stderr=subprocess.PIPE, text=True, timeout=120
                    )
                if res.returncode == 0:
                    size_kb = os.path.getsize(save_path) / 1024
                    write_log(f"Respaldo completado: {save_path} ({size_kb:.1f} KB)")
                    self.safe_after(0, lambda: messagebox.showinfo(
                        "Exportación Exitosa",
                        f"Respaldo de '{target_db}' guardado correctamente.\n\n"
                        f"Archivo: {os.path.basename(save_path)}\nTamaño: {size_kb:.1f} KB"
                    ))
                    self.safe_after(0, lambda: self.send_notification(f"Exportación de '{target_db}' completada"))
                else:
                    err = res.stderr.strip()
                    write_log(f"Error en mysqldump: {err}")
                    if "access denied" in err.lower():
                        err_user = "Acceso denegado: root requiere contraseña o tiene permisos restringidos."
                    else:
                        err_user = f"mysqldump falló:\n{err}"
                    self.safe_after(0, lambda: messagebox.showerror("Error de Exportación", err_user))
            except Exception as e:
                write_log(f"Excepción en exportación: {e}")
                self.safe_after(0, lambda: messagebox.showerror("Error", f"Error al exportar:\n{e}"))
            finally:
                self.safe_after(0, self.hide_progress)

        threading.Thread(target=run_export, daemon=True).start()

    def import_sql_file(self):
        """Importa un archivo SQL (.sql) a una base de datos MySQL."""
        if not self._port_open("127.0.0.1", 3306):
            messagebox.showwarning("MySQL inactivo", "Inicia MySQL antes de importar un archivo SQL.")
            return

        from tkinter import filedialog, simpledialog
        sql_file = filedialog.askopenfilename(
            title="Seleccionar archivo SQL para importar",
            filetypes=[("Archivos SQL", "*.sql"), ("Todos los archivos", "*.*")]
        )
        if not sql_file or not os.path.isfile(sql_file):
            return

        databases = self._list_mysql_databases()
        suggested_name = os.path.splitext(os.path.basename(sql_file))[0].split("_")[0]
        suggested_name = re.sub(r'[^a-zA-Z0-9_]', '', suggested_name)

        target_db = simpledialog.askstring(
            "Base de datos de destino",
            f"Bases de datos existentes: {', '.join(databases) if databases else 'ninguna'}\n\n"
            "Introduce el nombre de la base de datos donde importar:",
            initialvalue=suggested_name if suggested_name else "mi_base",
            parent=self.root
        )
        if not target_db:
            return
        target_db = target_db.strip()
        if not re.match(r'^[a-zA-Z0-9_]+$', target_db):
            messagebox.showerror("Nombre inválido", "El nombre de la base de datos contiene caracteres no válidos.")
            return

        mysql_bin = self._get_mysql_bin("mysql")

        if databases and target_db not in databases:
            if messagebox.askyesno("Crear Base de Datos", f"La base de datos '{target_db}' no existe.\n¿Deseas crearla ahora?"):
                res_create = subprocess.run(
                    [mysql_bin, "-u", "root", "-e", f"CREATE DATABASE `{target_db}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"],
                    capture_output=True, text=True
                )
                if res_create.returncode != 0:
                    messagebox.showerror("Error", f"No se pudo crear la base de datos:\n{res_create.stderr.strip()}")
                    return
            else:
                return

        self.show_progress()
        self.send_notification(f"Importando SQL en '{target_db}'...")
        write_log(f"Importando {sql_file} en base de datos '{target_db}'")

        def run_import():
            try:
                import_cmd = [mysql_bin, "-u", "root", "--default-character-set=utf8mb4", target_db]
                with open(sql_file, "r", encoding="utf-8", errors="replace") as in_f:
                    res = subprocess.run(
                        import_cmd,
                        stdin=in_f, capture_output=True, text=True, timeout=300
                    )
                if res.returncode == 0:
                    write_log(f"Importación completada con éxito en '{target_db}'")
                    self.safe_after(0, lambda: messagebox.showinfo(
                        "Importación Exitosa",
                        f"El archivo '{os.path.basename(sql_file)}' se importó correctamente en '{target_db}'."
                    ))
                    self.safe_after(0, lambda: self.send_notification(f"Importación en '{target_db}' completada"))
                else:
                    err = res.stderr.strip()
                    write_log(f"Error importando SQL: {err}")
                    self.safe_after(0, lambda: messagebox.showerror("Error de Importación", f"MySQL devolvió un error:\n{err}"))
            except Exception as e:
                write_log(f"Excepción en importación SQL: {e}")
                self.safe_after(0, lambda: messagebox.showerror("Error", f"Error al importar archivo SQL:\n{e}"))
            finally:
                self.safe_after(0, self.hide_progress)

        threading.Thread(target=run_import, daemon=True).start()

    # =========================================================================
    # Herramientas de Mantenimiento y Janitor
    # =========================================================================

    def purge_server_logs(self):
        """Purga y vacía los logs del servidor XAMPP para liberar espacio."""
        log_files = [
            "/opt/lampp/logs/access_log",
            "/opt/lampp/logs/error_log",
            "/opt/lampp/logs/php_error_log",
            "/opt/lampp/logs/ssl_request_log",
            "/opt/lampp/var/mysql/mysql.log",
        ]
        
        found = []
        total_bytes = 0
        for path in log_files:
            if os.path.isfile(path):
                sz = os.path.getsize(path)
                total_bytes += sz
                found.append((path, sz))
                
        if not found or total_bytes == 0:
            messagebox.showinfo("Logs limpios", "Los logs del servidor ya están limpios o vacíos (0 KB).")
            return
            
        mb = total_bytes / (1024 * 1024)
        msg = f"Se encontraron {len(found)} archivos de registro ({mb:.2f} MB en total):\n\n"
        for path, sz in found:
            msg += f"• {os.path.basename(path)}: {sz / 1024:.1f} KB\n"
        msg += "\n¿Deseas vaciar estos archivos para liberar espacio en disco?"
        
        if not messagebox.askyesno("Confirmar purga de logs", msg):
            return
            
        try:
            cleared_with_perm = True
            for path, _ in found:
                try:
                    with open(path, "w") as f:
                        f.truncate(0)
                except PermissionError:
                    cleared_with_perm = False
                    break
                    
            if not cleared_with_perm:
                target_str = " ".join(f"'{p}'" for p, _ in found)
                cmd = ["pkexec", "bash", "-c", f"for f in {target_str}; do : > \"$f\"; done"]
                subprocess.run(cmd, check=True, timeout=15)
                
            write_log(f"Logs de servidor purgados ({mb:.2f} MB liberados)")
            self.send_notification(f"Logs purgados: {mb:.2f} MB liberados")
            messagebox.showinfo("Purga completada", f"Se han vaciado los archivos de registro.\nEspacio liberado: {mb:.2f} MB.")
        except Exception as e:
            write_log(f"Error purgando logs: {e}")
            messagebox.showerror("Error", f"No se pudieron vaciar los logs:\n{e}")

    def clean_temp_sessions(self):
        """Limpia los archivos de sesiones temporales acumulados en /opt/lampp/temp."""
        temp_dir = "/opt/lampp/temp"
        if not os.path.isdir(temp_dir):
            messagebox.showinfo("Directorio temporal", "No se encontró el directorio /opt/lampp/temp.")
            return

        session_files = []
        total_bytes = 0
        try:
            for entry in os.scandir(temp_dir):
                if entry.is_file() and (entry.name.startswith("sess_") or entry.name.endswith(".tmp")):
                    try:
                        sz = entry.stat().st_size
                        total_bytes += sz
                        session_files.append(entry.path)
                    except Exception:
                        pass
        except Exception as e:
            write_log(f"Error escaneando temp: {e}")

        if not session_files:
            messagebox.showinfo("Sesiones temporales", "No hay archivos de sesiones temporales acumulados.")
            return

        kb = total_bytes / 1024
        if not messagebox.askyesno(
            "Limpiar temporales",
            f"Se encontraron {len(session_files)} archivos temporales de sesión ({kb:.1f} KB).\n\n"
            "¿Deseas eliminarlos para mantener limpio el entorno?"
        ):
            return

        deleted = 0
        direct_ok = True
        for path in session_files:
            try:
                os.remove(path)
                deleted += 1
            except PermissionError:
                direct_ok = False
                break
            except Exception:
                pass

        if not direct_ok:
            try:
                cmd = ["pkexec", "bash", "-c", f"rm -f {temp_dir}/sess_* {temp_dir}/*.tmp"]
                subprocess.run(cmd, check=True, timeout=15)
                deleted = len(session_files)
            except Exception as e:
                write_log(f"Error eliminando temporales vía pkexec: {e}")
                messagebox.showerror("Error", f"No se pudieron eliminar todos los temporales:\n{e}")
                return

        write_log(f"Archivos temporales eliminados: {deleted} ({kb:.1f} KB)")
        self.send_notification(f"{deleted} archivos temporales eliminados")
        messagebox.showinfo("Limpieza completada", f"Se eliminaron {deleted} archivos de sesión ({kb:.1f} KB liberados).")

    def check_disk_health(self):
        """Muestra el estado del disco, espacio libre y permisos del directorio de proyectos."""
        t = THEMES[self.current_theme]
        win = tk.Toplevel(self.root)
        win.title("Estado del Disco y Entorno")
        win.geometry("450x380")
        win.resizable(False, False)
        win.transient(self.root)
        win.configure(bg=t["bg"])

        check_path = "/opt/lampp" if os.path.exists("/opt/lampp") else "/"
        try:
            usage = shutil.disk_usage(check_path)
            total_gb = usage.total / (1024**3)
            used_gb = usage.used / (1024**3)
            free_gb = usage.free / (1024**3)
            pct = (usage.used / usage.total) * 100
        except Exception:
            total_gb = used_gb = free_gb = pct = 0

        htdocs_writable = os.access(HTDOCS_PATH, os.W_OK) if os.path.exists(HTDOCS_PATH) else False

        tk.Label(win, text="Diagnóstico del Entorno XAMPP", font=("Helvetica", 12, "bold"),
                 bg=t["bg"], fg=t["fg_label"]).pack(pady=(15, 10))

        frame = tk.Frame(win, bg=t["bg_secondary"], padx=15, pady=12)
        frame.pack(fill="both", expand=True, padx=15, pady=5)

        tk.Label(frame, text=f"Almacenamiento ({check_path}):", font=("Helvetica", 9, "bold"),
                 bg=t["bg_secondary"], fg=t["fg"]).pack(anchor="w", pady=(0, 4))
        
        info_disk = f"• Total: {total_gb:.1f} GB\n• Usado: {used_gb:.1f} GB ({pct:.1f}%)\n• Libre: {free_gb:.1f} GB"
        tk.Label(frame, text=info_disk, justify="left", font=("Monospace", 9),
                 bg=t["bg_secondary"], fg=t["fg"]).pack(anchor="w", padx=10, pady=(0, 6))

        pbar = ttk.Progressbar(frame, value=pct, maximum=100)
        pbar.pack(fill="x", padx=10, pady=(0, 15))

        tk.Label(frame, text="Permisos de htdocs:", font=("Helvetica", 9, "bold"),
                 bg=t["bg_secondary"], fg=t["fg"]).pack(anchor="w", pady=(0, 4))

        if htdocs_writable:
            perm_text = "✅ Tu usuario tiene permisos directos de escritura en htdocs.\n(Puedes crear proyectos sin usar sudo)."
            perm_color = t["fg_active"]
        else:
            perm_text = "⚠️ Tu usuario no tiene permisos de escritura en htdocs.\nPara solucionar esto, ejecuta en tu terminal:\nsudo chown -R $USER:$USER /opt/lampp/htdocs"
            perm_color = t.get("fg_conflict", "#f39c12")

        tk.Label(frame, text=perm_text, justify="left", font=("Helvetica", 8),
                 bg=t["bg_secondary"], fg=perm_color).pack(anchor="w", padx=10, pady=(0, 10))

        tk.Button(win, text="Cerrar", bg=t["bg_button"], fg=t["fg"],
                  font=("Helvetica", 9, "bold"), command=win.destroy).pack(pady=10)

    def show_php_tweaks_dialog(self):
        """Muestra ventana modal para ajustar parámetros comunes de php.ini."""
        php_ini_path = "/opt/lampp/etc/php.ini"
        if not os.path.isfile(php_ini_path):
            messagebox.showerror("php.ini no encontrado", f"No se encontró el archivo:\n{php_ini_path}")
            return

        try:
            with open(php_ini_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            messagebox.showerror("Error de lectura", f"No se pudo leer php.ini:\n{e}")
            return

        directives = {
            "upload_max_filesize": r"^\s*upload_max_filesize\s*=\s*([^\s;]+)",
            "post_max_size": r"^\s*post_max_size\s*=\s*([^\s;]+)",
            "memory_limit": r"^\s*memory_limit\s*=\s*([^\s;]+)",
            "max_execution_time": r"^\s*max_execution_time\s*=\s*([^\s;]+)",
        }

        current_values = {}
        for key, pattern in directives.items():
            m = re.search(pattern, content, flags=re.MULTILINE)
            current_values[key] = m.group(1) if m else ""

        t = THEMES[self.current_theme]
        win = tk.Toplevel(self.root)
        win.title("Ajustes Rápidos de PHP (php.ini)")
        win.geometry("380x310")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        win.configure(bg=t["bg"])

        tk.Label(win, text="Parámetros Rápidos de PHP", font=("Helvetica", 11, "bold"),
                 bg=t["bg"], fg=t["fg_label"]).pack(pady=(12, 8))

        form_frame = tk.Frame(win, bg=t["bg"], padx=15)
        form_frame.pack(fill="both", expand=True)

        entries = {}
        labels_desc = {
            "upload_max_filesize": "Subida máx. archivo (ej: 64M):",
            "post_max_size": "POST máx. tamaño (ej: 64M):",
            "memory_limit": "Límite de memoria (ej: 256M):",
            "max_execution_time": "Tiempo ejec. segs (ej: 300):",
        }

        for idx, (key, desc) in enumerate(labels_desc.items()):
            tk.Label(form_frame, text=desc, font=("Helvetica", 9), anchor="w",
                     bg=t["bg"], fg=t["fg"]).grid(row=idx, column=0, sticky="w", pady=4)
            ent = tk.Entry(form_frame, width=12, font=("Monospace", 9))
            ent.insert(0, current_values.get(key, ""))
            ent.grid(row=idx, column=1, sticky="e", pady=4, padx=(10, 0))
            entries[key] = ent

        def save_changes():
            new_content = content
            for key, ent in entries.items():
                val = ent.get().strip()
                if not val:
                    continue
                if not re.match(r'^[0-9]+[KMGkmg]?$', val):
                    messagebox.showerror("Valor inválido", f"Valor no válido para {key}: '{val}'")
                    return
                val = val.upper()
                pattern = rf"(^\s*{key}\s*=\s*)([^\s;]+)"
                if re.search(pattern, new_content, flags=re.MULTILINE):
                    new_content = re.sub(pattern, rf"\g<1>{val}", new_content, flags=re.MULTILINE)
                else:
                    new_content += f"\n{key} = {val}\n"

            try:
                written = False
                try:
                    with open(php_ini_path + ".bak", "w", encoding="utf-8") as bkp:
                        bkp.write(content)
                    with open(php_ini_path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    written = True
                except PermissionError:
                    written = False

                if not written:
                    tmp_file = "/tmp/php_ini_tweaked.tmp"
                    with open(tmp_file, "w", encoding="utf-8") as tmp:
                        tmp.write(new_content)
                    subprocess.run(["pkexec", "cp", tmp_file, php_ini_path], check=True, timeout=15)
                    try:
                        os.remove(tmp_file)
                    except Exception:
                        pass

                write_log("Valores de php.ini actualizados correctamente")
                self.send_notification("php.ini actualizado")
                messagebox.showinfo(
                    "Cambios guardados",
                    "Los ajustes de php.ini se han guardado exitosamente.\n\n"
                    "Reinicia el servicio Apache para que los cambios surtan efecto."
                )
                win.destroy()
            except Exception as e:
                write_log(f"Error guardando php.ini: {e}")
                messagebox.showerror("Error", f"No se pudo guardar php.ini:\n{e}")

        btn_box = tk.Frame(win, bg=t["bg"])
        btn_box.pack(pady=12)

        tk.Button(btn_box, text="💾 Guardar Cambios", bg=t["btn_start"], fg="white",
                  font=("Helvetica", 9, "bold"), command=save_changes).pack(side="left", padx=5)
        tk.Button(btn_box, text="Cancelar", bg=t["bg_button"], fg=t["fg"],
                  font=("Helvetica", 9), command=win.destroy).pack(side="left", padx=5)

    # =========================================================================
    # Administrador de Virtual Hosts (VHosts)
    # =========================================================================

    def _is_vhosts_enabled(self):
        """Comprueba si Include etc/extra/httpd-vhosts.conf está activo en httpd.conf."""
        httpd_conf = "/opt/lampp/etc/httpd.conf"
        if not os.path.isfile(httpd_conf):
            return False
        try:
            with open(httpd_conf, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            return bool(re.search(r'^\s*Include\s+etc/extra/httpd-vhosts\.conf', content, re.MULTILINE))
        except Exception:
            return False

    def _enable_vhosts_in_httpd_conf(self):
        """Habilita la directiva Include etc/extra/httpd-vhosts.conf en httpd.conf."""
        httpd_conf = "/opt/lampp/etc/httpd.conf"
        if not os.path.isfile(httpd_conf):
            messagebox.showerror("Error", f"No se encontró {httpd_conf}")
            return False

        try:
            with open(httpd_conf, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            pattern = r'^\s*#\s*(Include\s+etc/extra/httpd-vhosts\.conf)'
            if re.search(pattern, content, re.MULTILINE):
                new_content = re.sub(pattern, r'\g<1>', content, flags=re.MULTILINE)
            elif "Include etc/extra/httpd-vhosts.conf" in content:
                return True
            else:
                new_content = content + "\n# Virtual hosts\nInclude etc/extra/httpd-vhosts.conf\n"

            try:
                with open(httpd_conf + ".bak", "w", encoding="utf-8") as bkp:
                    bkp.write(content)
                with open(httpd_conf, "w", encoding="utf-8") as f:
                    f.write(new_content)
            except PermissionError:
                tmp = "/tmp/httpd_vhosts_enable.tmp"
                with open(tmp, "w", encoding="utf-8") as t:
                    t.write(new_content)
                subprocess.run(["pkexec", "cp", tmp, httpd_conf], check=True, timeout=15)
                try:
                    os.remove(tmp)
                except Exception:
                    pass

            write_log("Virtual hosts habilitado en httpd.conf")
            return True
        except Exception as e:
            write_log(f"Error habilitando vhosts en httpd.conf: {e}")
            messagebox.showerror("Error", f"No se pudo modificar httpd.conf:\n{e}")
            return False

    def _parse_vhosts_file(self):
        """Lee y analiza las directivas de VirtualHost definidas en httpd-vhosts.conf."""
        vhosts_conf = "/opt/lampp/etc/extra/httpd-vhosts.conf"
        if not os.path.isfile(vhosts_conf):
            return []

        try:
            with open(vhosts_conf, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            write_log(f"Error leyendo {vhosts_conf}: {e}")
            return []

        vhosts = []
        pattern = r'<VirtualHost\s+([^>]+)>(.*?)</VirtualHost>'
        for match in re.finditer(pattern, content, re.DOTALL | re.IGNORECASE):
            port_info = match.group(1).strip()
            block = match.group(2)
            
            m_name = re.search(r'^\s*ServerName\s+([^\s#]+)', block, re.MULTILINE | re.IGNORECASE)
            m_doc = re.search(r'^\s*DocumentRoot\s+["\']?([^"\'#\s]+)', block, re.MULTILINE | re.IGNORECASE)
            m_alias = re.search(r'^\s*ServerAlias\s+([^\s#]+)', block, re.MULTILINE | re.IGNORECASE)
            
            if m_name and m_doc:
                vhosts.append({
                    "port": port_info,
                    "server_name": m_name.group(1),
                    "doc_root": m_doc.group(1),
                    "alias": m_alias.group(1) if m_alias else "",
                    "raw": match.group(0)
                })
        return vhosts

    def show_vhosts_manager(self):
        """Muestra el administrador de Virtual Hosts."""
        t = THEMES[self.current_theme]
        win = tk.Toplevel(self.root)
        win.title("Administrador de Virtual Hosts (VHosts)")
        win.geometry("640x480")
        win.resizable(False, False)
        win.transient(self.root)
        win.configure(bg=t["bg"])

        is_enabled = self._is_vhosts_enabled()
        status_frame = tk.Frame(win, bg=t["bg_secondary"], padx=10, pady=8)
        status_frame.pack(fill="x", padx=12, pady=(12, 6))

        lbl_status = tk.Label(status_frame, 
                              text="✅ Soporte de Virtual Hosts activo en httpd.conf" if is_enabled else "⚠️ Virtual Hosts deshabilitado en httpd.conf",
                              font=("Helvetica", 9, "bold"),
                              bg=t["bg_secondary"], 
                              fg=t["fg_active"] if is_enabled else t.get("fg_conflict", "#f39c12"))
        lbl_status.pack(side="left")

        def enable_now():
            if self._enable_vhosts_in_httpd_conf():
                lbl_status.configure(text="✅ Soporte de Virtual Hosts activo en httpd.conf", fg=t["fg_active"])
                btn_enable.pack_forget()
                self.send_notification("Virtual hosts habilitado en httpd.conf")
                messagebox.showinfo("Éxito", "Se habilitó 'Include etc/extra/httpd-vhosts.conf'.\nReinicia Apache para aplicar.")

        btn_enable = tk.Button(status_frame, text="Habilitar en httpd.conf", bg=t["btn_start"], fg="white",
                               font=("Helvetica", 8, "bold"), command=enable_now)
        if not is_enabled:
            btn_enable.pack(side="right")

        tree_frame = tk.Frame(win, bg=t["bg"])
        tree_frame.pack(fill="both", expand=True, padx=12, pady=6)

        cols = ("Dominio", "DocumentRoot", "Puerto")
        tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=10)
        tree.heading("Dominio", text="Dominio (ServerName)")
        tree.heading("DocumentRoot", text="Carpeta Raíz (DocumentRoot)")
        tree.heading("Puerto", text="Puerto")

        tree.column("Dominio", width=180)
        tree.column("DocumentRoot", width=340)
        tree.column("Puerto", width=70, anchor="center")

        tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        def refresh_tree():
            for item in tree.get_children():
                tree.delete(item)
            for vh in self._parse_vhosts_file():
                tree.insert("", "end", values=(vh["server_name"], vh["doc_root"], vh["port"]))

        refresh_tree()

        btn_bar = tk.Frame(win, bg=t["bg"])
        btn_bar.pack(fill="x", padx=12, pady=(6, 12))

        def on_add():
            self.create_vhost_dialog(on_created=lambda: (refresh_tree(), self.send_notification("Virtual Host creado")))

        def on_open_browser():
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("Seleccionar", "Selecciona un Virtual Host de la lista.")
                return
            item = tree.item(sel[0])
            domain = item["values"][0]
            webbrowser.open(f"http://{domain}")

        def on_delete():
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("Seleccionar", "Selecciona un Virtual Host para eliminar.")
                return
            item = tree.item(sel[0])
            domain = item["values"][0]
            if messagebox.askyesno("Confirmar eliminación", f"¿Eliminar el Virtual Host '{domain}' de httpd-vhosts.conf?"):
                vhosts_file = "/opt/lampp/etc/extra/httpd-vhosts.conf"
                try:
                    with open(vhosts_file, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    pattern = rf'<VirtualHost\s+[^>]+>(?:(?!</VirtualHost>).)*ServerName\s+{re.escape(domain)}.*?</VirtualHost>\s*'
                    new_content = re.sub(pattern, "", content, flags=re.DOTALL | re.IGNORECASE)
                    
                    try:
                        with open(vhosts_file, "w", encoding="utf-8") as f:
                            f.write(new_content)
                    except PermissionError:
                        tmp = "/tmp/vhosts_del.tmp"
                        with open(tmp, "w", encoding="utf-8") as t:
                            t.write(new_content)
                        subprocess.run(["pkexec", "cp", tmp, vhosts_file], check=True, timeout=15)
                        try:
                            os.remove(tmp)
                        except Exception:
                            pass

                    if messagebox.askyesno("/etc/hosts", f"¿Deseas también remover '{domain}' de /etc/hosts?"):
                        try:
                            with open("/etc/hosts", "r", encoding="utf-8") as hf:
                                hosts_txt = hf.read()
                            new_hosts = re.sub(rf'^.*?\b{re.escape(domain)}\b.*?\n', '', hosts_txt, flags=re.MULTILINE)
                            tmp_h = "/tmp/hosts_cleaned.tmp"
                            with open(tmp_h, "w", encoding="utf-8") as th:
                                th.write(new_hosts)
                            subprocess.run(["pkexec", "cp", tmp_h, "/etc/hosts"], check=True, timeout=15)
                            try:
                                os.remove(tmp_h)
                            except Exception:
                                pass
                        except Exception as eh:
                            write_log(f"Error limpiando /etc/hosts: {eh}")

                    write_log(f"Virtual Host '{domain}' eliminado.")
                    refresh_tree()
                    messagebox.showinfo("Eliminado", f"Virtual Host '{domain}' eliminado correctamente.")
                except Exception as e:
                    write_log(f"Error eliminando vhost: {e}")
                    messagebox.showerror("Error", f"No se pudo eliminar el vhost:\n{e}")

        tk.Button(btn_bar, text="➕ Crear Virtual Host...", bg=t["btn_start"], fg="white",
                  font=("Helvetica", 9, "bold"), command=on_add).pack(side="left", padx=3)
        tk.Button(btn_bar, text="🌐 Abrir en Navegador", bg=t["bg_button"], fg=t["fg"],
                  font=("Helvetica", 9), command=on_open_browser).pack(side="left", padx=3)
        tk.Button(btn_bar, text="🗑 Eliminar VHost", bg=t["btn_stop"], fg="white",
                  font=("Helvetica", 9), command=on_delete).pack(side="left", padx=3)
        tk.Button(btn_bar, text="Cerrar", bg=t["bg_button"], fg=t["fg"],
                  font=("Helvetica", 9), command=win.destroy).pack(side="right", padx=3)

    def create_vhost_dialog(self, on_created=None):
        """Asistente para crear un nuevo Virtual Host y registrarlo en /etc/hosts."""
        t = THEMES[self.current_theme]
        dlg = tk.Toplevel(self.root)
        dlg.title("Nuevo Virtual Host")
        dlg.geometry("460x360")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.configure(bg=t["bg"])

        tk.Label(dlg, text="Configurar Nuevo Virtual Host", font=("Helvetica", 11, "bold"),
                 bg=t["bg"], fg=t["fg_label"]).pack(pady=(12, 8))

        form = tk.Frame(dlg, bg=t["bg"], padx=15)
        form.pack(fill="both", expand=True)

        tk.Label(form, text="Nombre de dominio (ej: miapp.test):", font=("Helvetica", 9),
                 bg=t["bg"], fg=t["fg"], anchor="w").grid(row=0, column=0, sticky="w", pady=4)
        ent_domain = tk.Entry(form, width=30, font=("Helvetica", 9))
        ent_domain.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 6))

        tk.Label(form, text="Directorio del proyecto:", font=("Helvetica", 9),
                 bg=t["bg"], fg=t["fg"], anchor="w").grid(row=2, column=0, sticky="w", pady=4)
        
        path_frame = tk.Frame(form, bg=t["bg"])
        path_frame.grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 6))

        project_choices = getattr(self, "projects", [])
        combo_proj = ttk.Combobox(path_frame, values=project_choices, width=22)
        combo_proj.pack(side="left")

        def on_browse_folder():
            from tkinter import filedialog
            chosen = filedialog.askdirectory(initialdir=HTDOCS_PATH, title="Seleccionar carpeta de proyecto")
            if chosen:
                ent_custom_path.delete(0, tk.END)
                ent_custom_path.insert(0, chosen)

        tk.Button(path_frame, text="Examinar...", font=("Helvetica", 8),
                  command=on_browse_folder).pack(side="left", padx=5)

        ent_custom_path = tk.Entry(form, width=38, font=("Monospace", 8))
        ent_custom_path.grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 6))

        def on_combo_select(event=None):
            selected = combo_proj.get().strip()
            if selected:
                full_p = os.path.join(HTDOCS_PATH, selected)
                ent_custom_path.delete(0, tk.END)
                ent_custom_path.insert(0, full_p)
                if not ent_domain.get().strip():
                    ent_domain.insert(0, f"{selected.lower()}.test")

        combo_proj.bind("<<ComboboxSelected>>", on_combo_select)

        var_public = tk.BooleanVar(value=True)
        chk_public = tk.Checkbutton(form, text="Usar subdirectorio /public si existe (Laravel)",
                                    variable=var_public, bg=t["bg"], fg=t["fg"],
                                    selectcolor=t["bg_secondary"], activebackground=t["bg"])
        chk_public.grid(row=5, column=0, columnspan=2, sticky="w", pady=2)

        var_hosts = tk.BooleanVar(value=True)
        chk_hosts = tk.Checkbutton(form, text="Añadir a /etc/hosts (127.0.0.1 dominio)",
                                   variable=var_hosts, bg=t["bg"], fg=t["fg"],
                                   selectcolor=t["bg_secondary"], activebackground=t["bg"])
        chk_hosts.grid(row=6, column=0, columnspan=2, sticky="w", pady=2)

        def save_vhost():
            domain = ent_domain.get().strip()
            proj_path = ent_custom_path.get().strip()

            if not domain or not re.match(r'^[a-zA-Z0-9.-]+$', domain):
                messagebox.showerror("Dominio inválido", "Introduce un dominio válido (ej: app.test o sitio.local).")
                return

            if not proj_path or not os.path.isdir(proj_path):
                messagebox.showerror("Ruta inválida", "Selecciona una carpeta de proyecto válida.")
                return

            doc_root = proj_path
            if var_public.get() and os.path.isdir(os.path.join(proj_path, "public")):
                doc_root = os.path.join(proj_path, "public")

            stanza = (
                f"\n# Virtual Host para {domain}\n"
                f"<VirtualHost *:80>\n"
                f"    ServerAdmin webmaster@{domain}\n"
                f"    DocumentRoot \"{doc_root}\"\n"
                f"    ServerName {domain}\n"
                f"    ServerAlias www.{domain}\n"
                f"    <Directory \"{doc_root}\">\n"
                f"        Options Indexes FollowSymLinks MultiViews\n"
                f"        AllowOverride All\n"
                f"        Require all granted\n"
                f"    </Directory>\n"
                f"    ErrorLog \"logs/{domain}-error_log\"\n"
                f"    CustomLog \"logs/{domain}-access_log\" common\n"
                f"</VirtualHost>\n"
            )

            vhosts_file = "/opt/lampp/etc/extra/httpd-vhosts.conf"
            try:
                if not self._is_vhosts_enabled():
                    self._enable_vhosts_in_httpd_conf()

                try:
                    with open(vhosts_file, "a", encoding="utf-8") as f:
                        f.write(stanza)
                except PermissionError:
                    tmp = "/tmp/vhost_add.tmp"
                    current = ""
                    if os.path.isfile(vhosts_file):
                        with open(vhosts_file, "r", encoding="utf-8", errors="replace") as cf:
                            current = cf.read()
                    with open(tmp, "w", encoding="utf-8") as t:
                        t.write(current + stanza)
                    subprocess.run(["pkexec", "cp", tmp, vhosts_file], check=True, timeout=15)
                    try:
                        os.remove(tmp)
                    except Exception:
                        pass

                if var_hosts.get():
                    hosts_entry = f"127.0.0.1\t{domain}\twww.{domain}\n"
                    with open("/etc/hosts", "r", encoding="utf-8", errors="replace") as hf:
                        h_content = hf.read()
                    if domain not in h_content:
                        cmd = ["pkexec", "bash", "-c", f"echo -e '{hosts_entry}' >> /etc/hosts"]
                        subprocess.run(cmd, check=True, timeout=15)

                write_log(f"Virtual Host '{domain}' creado con éxito.")
                messagebox.showinfo("Éxito", f"Virtual Host '{domain}' configurado correctamente.")
                if on_created:
                    on_created()
                dlg.destroy()

                if messagebox.askyesno("Reiniciar Apache", "¿Deseas reiniciar Apache ahora para que el nuevo dominio tome efecto?"):
                    self.run_service("restart", "apache")
            except Exception as e:
                write_log(f"Error creando Virtual Host: {e}")
                messagebox.showerror("Error", f"No se pudo crear el Virtual Host:\n{e}")

        btn_box = tk.Frame(dlg, bg=t["bg"])
        btn_box.pack(pady=10)

        tk.Button(btn_box, text="💾 Crear y Configurar", bg=t["btn_start"], fg="white",
                  font=("Helvetica", 9, "bold"), command=save_vhost).pack(side="left", padx=5)
        tk.Button(btn_box, text="Cancelar", bg=t["bg_button"], fg=t["fg"],
                  font=("Helvetica", 9), command=dlg.destroy).pack(side="left", padx=5)

    # =========================================================================
    # Asistente de Resolución de Conflictos y Extensiones PHP
    # =========================================================================

    def show_conflict_resolver(self):
        """Asistente de diagnóstico y resolución de conflictos de puertos."""
        t = THEMES[self.current_theme]
        win = tk.Toplevel(self.root)
        win.title("Asistente de Resolución de Conflictos")
        win.geometry("520x420")
        win.resizable(False, False)
        win.transient(self.root)
        win.configure(bg=t["bg"])

        tk.Label(win, text="Diagnóstico de Puertos y Conflictos", font=("Helvetica", 12, "bold"),
                 bg=t["bg"], fg=t["fg_label"]).pack(pady=(12, 6))

        frame = tk.Frame(win, bg=t["bg_secondary"], padx=15, pady=12)
        frame.pack(fill="both", expand=True, padx=15, pady=6)

        conflicts = []

        if self._port_open("127.0.0.1", 80) and not _is_service_running(ALL_SERVICES["Apache"]):
            culprit = "desconocido"
            try:
                res = subprocess.run(["systemctl", "is-active", "apache2"], capture_output=True, text=True)
                if res.stdout.strip() == "active":
                    culprit = "apache2 (servicio nativo de Linux Mint / Ubuntu)"
                else:
                    res_ng = subprocess.run(["systemctl", "is-active", "nginx"], capture_output=True, text=True)
                    if res_ng.stdout.strip() == "active":
                        culprit = "nginx (servidor web del sistema)"
            except Exception:
                pass
            conflicts.append({"service": "Apache", "port": 80, "culprit": culprit, "sys_service": "apache2"})

        if self._port_open("127.0.0.1", 3306) and not _is_service_running(ALL_SERVICES["MySQL"]):
            culprit_db = "desconocido"
            sys_db = "mariadb"
            try:
                res_m = subprocess.run(["systemctl", "is-active", "mariadb"], capture_output=True, text=True)
                if res_m.stdout.strip() == "active":
                    culprit_db = "mariadb (servidor de base de datos nativo)"
                    sys_db = "mariadb"
                else:
                    res_my = subprocess.run(["systemctl", "is-active", "mysql"], capture_output=True, text=True)
                    if res_my.stdout.strip() == "active":
                        culprit_db = "mysql (servidor nativo del sistema)"
                        sys_db = "mysql"
            except Exception:
                pass
            conflicts.append({"service": "MySQL", "port": 3306, "culprit": culprit_db, "sys_service": sys_db})

        if not conflicts:
            tk.Label(frame, text="✅ No se han detectado conflictos en los puertos principales.",
                     font=("Helvetica", 10, "bold"), bg=t["bg_secondary"], fg=t["fg_active"]).pack(pady=20)
            tk.Label(frame, text="Los puertos 80 (Apache) y 3306 (MySQL) están completamente\nlibres o siendo utilizados por XAMPP correctamente.",
                     font=("Helvetica", 9), bg=t["bg_secondary"], fg=t["fg"]).pack()
        else:
            tk.Label(frame, text="⚠️ Se detectaron servicios del sistema bloqueando XAMPP:",
                     font=("Helvetica", 10, "bold"), bg=t["bg_secondary"], fg=t.get("fg_conflict", "#f39c12")).pack(anchor="w", pady=(0, 10))

            for conf in conflicts:
                card = tk.Frame(frame, bg=t["bg"], padx=10, pady=8, highlightbackground="#313244", highlightthickness=1)
                card.pack(fill="x", pady=5)

                txt = f"• Puerto {conf['port']} ({conf['service']}): Ocupado por {conf['culprit']}."
                tk.Label(card, text=txt, font=("Helvetica", 9, "bold"), bg=t["bg"], fg=t["fg"], wraplength=440, justify="left").pack(anchor="w")

                def resolve(sys_svc=conf["sys_service"]):
                    if messagebox.askyesno(
                        "Desactivar servicio",
                        f"¿Detener y deshabilitar '{sys_svc}' del sistema para permitir que XAMPP funcione?\n\n"
                        f"Comando: pkexec systemctl stop {sys_svc} && pkexec systemctl disable {sys_svc}"
                    ):
                        try:
                            subprocess.run(["pkexec", "bash", "-c", f"systemctl stop {sys_svc} && systemctl disable {sys_svc}"], check=True, timeout=15)
                            write_log(f"Servicio del sistema {sys_svc} detenido y desactivado.")
                            self.send_notification(f"{sys_svc} detenido.")
                            messagebox.showinfo("Resuelto", f"Se detuvo '{sys_svc}'.\nAhora puedes iniciar XAMPP.")
                            win.destroy()
                            self.update_status()
                        except Exception as ex:
                            write_log(f"Error deteniendo {sys_svc}: {ex}")
                            messagebox.showerror("Error", f"No se pudo detener {sys_svc}:\n{ex}")

                tk.Button(card, text=f"Detener y desactivar {conf['sys_service']} del sistema",
                          bg=t["btn_start"], fg="white", font=("Helvetica", 8, "bold"),
                          command=resolve).pack(anchor="w", pady=(5, 0))

        tk.Button(win, text="Cerrar", bg=t["bg_button"], fg=t["fg"],
                  font=("Helvetica", 9), command=win.destroy).pack(pady=10)

    def show_php_extensions_dialog(self):
        """Muestra lista de extensiones de PHP activas y permite activarlas."""
        t = THEMES[self.current_theme]
        win = tk.Toplevel(self.root)
        win.title("Extensiones de PHP (Módulos)")
        win.geometry("480x420")
        win.resizable(False, False)
        win.transient(self.root)
        win.configure(bg=t["bg"])

        tk.Label(win, text="Módulos y Extensiones de PHP", font=("Helvetica", 11, "bold"),
                 bg=t["bg"], fg=t["fg_label"]).pack(pady=(12, 6))

        loaded_modules = set()
        php_bin = "/opt/lampp/bin/php"
        if os.path.isfile(php_bin):
            try:
                res = subprocess.run([php_bin, "-m"], capture_output=True, text=True, timeout=5)
                if res.returncode == 0:
                    loaded_modules = set(m.strip().lower() for m in res.stdout.splitlines() if m.strip())
            except Exception as e:
                write_log(f"Error listando módulos PHP: {e}")

        common_exts = [
            ("curl", "Cliente HTTP y peticiones cURL"),
            ("intl", "Internacionalización (requerido por Symfony/Laravel)"),
            ("mbstring", "Manejo de cadenas multibyte UTF-8"),
            ("openssl", "Criptografía y HTTPS seguro"),
            ("pdo_mysql", "Conector PDO MySQL/MariaDB"),
            ("mysqli", "Conector nativo MySQLi"),
            ("zip", "Compresión Zip (requerido por Composer)"),
            ("gd", "Manipulación y redimensionado de imágenes"),
            ("fileinfo", "Detección precisa de tipos MIME"),
            ("bcmath", "Matemáticas de precisión arbitraria"),
            ("soap", "Protocolo de servicios web SOAP"),
        ]

        frame_scroll = tk.Frame(win, bg=t["bg_secondary"], padx=10, pady=8)
        frame_scroll.pack(fill="both", expand=True, padx=12, pady=6)

        canvas = tk.Canvas(frame_scroll, bg=t["bg_secondary"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(frame_scroll, orient="vertical", command=canvas.yview)
        inner_frame = tk.Frame(canvas, bg=t["bg_secondary"])

        inner_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        php_ini_path = "/opt/lampp/etc/php.ini"

        def enable_extension(ext_name):
            if not os.path.isfile(php_ini_path):
                messagebox.showerror("Error", f"No se encontró {php_ini_path}")
                return
            try:
                with open(php_ini_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()

                pattern = rf'^\s*;\s*(extension\s*=\s*(?:php_)?{re.escape(ext_name)}(?:\.so|\.dll)?)'
                if re.search(pattern, content, re.MULTILINE):
                    new_content = re.sub(pattern, r'\g<1>', content, flags=re.MULTILINE)
                else:
                    new_content = content + f"\nextension={ext_name}.so\n"

                try:
                    with open(php_ini_path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                except PermissionError:
                    tmp = "/tmp/php_ext_enable.tmp"
                    with open(tmp, "w", encoding="utf-8") as t_f:
                        t_f.write(new_content)
                    subprocess.run(["pkexec", "cp", tmp, php_ini_path], check=True, timeout=15)
                    try:
                        os.remove(tmp)
                    except Exception:
                        pass

                write_log(f"Extensión PHP '{ext_name}' habilitada en php.ini")
                messagebox.showinfo("Éxito", f"Extensión '{ext_name}' activada en php.ini.\nReinicia Apache para que tome efecto.")
                win.destroy()
            except Exception as ex:
                write_log(f"Error activando extensión {ext_name}: {ex}")
                messagebox.showerror("Error", f"No se pudo modificar php.ini:\n{ex}")

        for ext_name, desc in common_exts:
            row = tk.Frame(inner_frame, bg=t["bg_secondary"], pady=4)
            row.pack(fill="x", padx=5)

            is_active = ext_name.lower() in loaded_modules
            badge_txt = "✅ Activa" if is_active else "⚪ Inactiva"
            badge_color = t["fg_active"] if is_active else t.get("fg_conflict", "#888888")

            tk.Label(row, text=badge_txt, font=("Helvetica", 8, "bold"),
                     bg=t["bg_secondary"], fg=badge_color, width=9, anchor="w").pack(side="left")
            
            tk.Label(row, text=f"{ext_name}:", font=("Monospace", 9, "bold"),
                     bg=t["bg_secondary"], fg=t["fg"], width=12, anchor="w").pack(side="left")

            tk.Label(row, text=desc, font=("Helvetica", 8),
                     bg=t["bg_secondary"], fg=t["fg"], anchor="w").pack(side="left", padx=5)

            if not is_active:
                tk.Button(row, text="Activar", font=("Helvetica", 7, "bold"),
                          bg=t["btn_start"], fg="white",
                          command=lambda e=ext_name: enable_extension(e)).pack(side="right", padx=4)

        tk.Button(win, text="Cerrar", bg=t["bg_button"], fg=t["fg"],
                  font=("Helvetica", 9), command=win.destroy).pack(pady=8)

    def install_desktop_shortcut(self):
        """Instala el acceso directo en el menú de aplicaciones de Linux Mint."""
        install_script = os.path.join(PROJECT_DIR, "install.sh")
        if os.path.isfile(install_script):
            try:
                res = subprocess.run(["bash", install_script], capture_output=True, text=True, timeout=10)
                if res.returncode == 0:
                    self.send_notification("Acceso directo instalado en el menú de Linux Mint")
                    messagebox.showinfo("Instalación Exitosa",
                                        "Se ha instalado el acceso directo en tu menú de aplicaciones.\n\n"
                                        "Busca 'XAMPP Control Center' en la categoría Desarrollo o Programación.")
                else:
                    messagebox.showerror("Error", f"Fallo al ejecutar instalador:\n{res.stderr}")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo ejecutar install.sh:\n{e}")
        else:
            messagebox.showerror("No encontrado", f"No se encontró el script instalador:\n{install_script}")

    # =========================================================================
    # v2.5: Generador SSL (HTTPS), Monitor de Telemetría, Snapshots y PHP Multi-Versión
    # =========================================================================

    def show_ssl_manager(self):
        """Asistente para generar certificados SSL locales y configurar HTTPS en Apache."""
        t = THEMES[self.current_theme]
        win = tk.Toplevel(self.root)
        win.title("Generador de Certificados SSL (HTTPS)")
        win.geometry("540x510")
        win.resizable(False, False)
        win.transient(self.root)
        win.configure(bg=t["bg"])

        tk.Label(win, text="Generador de Certificados SSL y HTTPS", font=("Helvetica", 12, "bold"),
                 bg=t["bg"], fg=t["fg_label"]).pack(pady=(12, 6))

        frame = tk.Frame(win, bg=t["bg"], padx=15)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="Dominio o Hostname local (ej: localhost o miapp.test):", font=("Helvetica", 9),
                 bg=t["bg"], fg=t["fg"]).grid(row=0, column=0, sticky="w", pady=4)
        ent_domain = tk.Entry(frame, width=32, font=("Helvetica", 9))
        ent_domain.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 6))
        ent_domain.insert(0, "localhost")

        tk.Label(frame, text="Días de validez:", font=("Helvetica", 9),
                 bg=t["bg"], fg=t["fg"]).grid(row=2, column=0, sticky="w", pady=4)
        ent_days = tk.Entry(frame, width=12, font=("Helvetica", 9))
        ent_days.grid(row=3, column=0, sticky="w", pady=(0, 6))
        ent_days.insert(0, "365")

        var_vhost_ssl = tk.BooleanVar(value=True)
        chk_vhost = tk.Checkbutton(frame, text="Crear VirtualHost SSL (*:443) en httpd-vhosts.conf",
                                   variable=var_vhost_ssl, bg=t["bg"], fg=t["fg"],
                                   selectcolor=t["bg_secondary"], activebackground=t["bg"])
        chk_vhost.grid(row=4, column=0, columnspan=2, sticky="w", pady=4)

        tk.Label(frame, text="Carpeta de proyecto (DocumentRoot):", font=("Helvetica", 9),
                 bg=t["bg"], fg=t["fg"]).grid(row=5, column=0, sticky="w", pady=4)
        
        path_frame = tk.Frame(frame, bg=t["bg"])
        path_frame.grid(row=6, column=0, columnspan=2, sticky="w", pady=(0, 6))

        project_choices = getattr(self, "projects", [])
        combo_proj = ttk.Combobox(path_frame, values=project_choices, width=22)
        combo_proj.pack(side="left")

        def on_browse():
            from tkinter import filedialog
            chosen = filedialog.askdirectory(initialdir=HTDOCS_PATH, title="Seleccionar DocumentRoot")
            if chosen:
                ent_doc.delete(0, tk.END)
                ent_doc.insert(0, chosen)

        tk.Button(path_frame, text="Examinar...", font=("Helvetica", 8), command=on_browse).pack(side="left", padx=5)

        ent_doc = tk.Entry(frame, width=42, font=("Monospace", 8))
        ent_doc.grid(row=7, column=0, columnspan=2, sticky="w", pady=(0, 6))
        ent_doc.insert(0, HTDOCS_PATH)

        def on_proj_change(e=None):
            sel = combo_proj.get().strip()
            if sel:
                full_p = os.path.join(HTDOCS_PATH, sel)
                if os.path.isdir(os.path.join(full_p, "public")):
                    full_p = os.path.join(full_p, "public")
                ent_doc.delete(0, tk.END)
                ent_doc.insert(0, full_p)
                if ent_domain.get().strip() in ("localhost", ""):
                    ent_domain.delete(0, tk.END)
                    ent_domain.insert(0, f"{sel.lower()}.test")

        combo_proj.bind("<<ComboboxSelected>>", on_proj_change)

        info_box = tk.Label(frame, text="", font=("Monospace", 8), bg=t["bg_secondary"],
                            fg=t["fg"], justify="left", wraplength=480, padx=8, pady=8)
        info_box.grid(row=8, column=0, columnspan=2, sticky="we", pady=8)
        info_box.grid_remove()

        def generate_ssl():
            domain = ent_domain.get().strip()
            days = ent_days.get().strip() or "365"
            doc_root = ent_doc.get().strip()

            if not domain or not re.match(r'^[a-zA-Z0-9.-]+$', domain):
                messagebox.showerror("Dominio inválido", "Introduce un dominio válido (ej: app.test o localhost).")
                return

            openssl_bin = shutil.which("openssl") or "/usr/bin/openssl"
            if not os.path.isfile(openssl_bin):
                messagebox.showerror("OpenSSL no encontrado", "No se encontró el comando 'openssl' en el sistema.")
                return

            tmp_key = f"/tmp/{domain}.key"
            tmp_crt = f"/tmp/{domain}.crt"

            cmd = [
                openssl_bin, "req", "-x509", "-nodes", "-days", str(days),
                "-newkey", "rsa:2048",
                "-keyout", tmp_key,
                "-out", tmp_crt,
                "-subj", f"/C=ES/ST=Local/L=Local/O=XAMPP-Local/CN={domain}",
                "-addext", f"subjectAltName=DNS:{domain},DNS:localhost,IP:127.0.0.1"
            ]

            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                if res.returncode != 0:
                    messagebox.showerror("Error OpenSSL", f"Falló al generar certificado:\n{res.stderr}")
                    return

                target_crt = f"/opt/lampp/etc/ssl.crt/{domain}.crt"
                target_key = f"/opt/lampp/etc/ssl.key/{domain}.key"

                for src, dst in [(tmp_crt, target_crt), (tmp_key, target_key)]:
                    try:
                        shutil.copy2(src, dst)
                    except PermissionError:
                        subprocess.run(["pkexec", "cp", src, dst], check=True, timeout=10)
                    try:
                        os.remove(src)
                    except Exception:
                        pass

                if var_vhost_ssl.get():
                    if not doc_root or not os.path.isdir(doc_root):
                        doc_root = HTDOCS_PATH

                    ssl_stanza = (
                        f"\n# VirtualHost SSL para {domain}\n"
                        f"<VirtualHost *:443>\n"
                        f"    ServerName {domain}\n"
                        f"    DocumentRoot \"{doc_root}\"\n"
                        f"    SSLEngine on\n"
                        f"    SSLCertificateFile \"{target_crt}\"\n"
                        f"    SSLCertificateKeyFile \"{target_key}\"\n"
                        f"    <Directory \"{doc_root}\">\n"
                        f"        Options Indexes FollowSymLinks MultiViews\n"
                        f"        AllowOverride All\n"
                        f"        Require all granted\n"
                        f"    </Directory>\n"
                        f"</VirtualHost>\n"
                    )

                    vhosts_file = "/opt/lampp/etc/extra/httpd-vhosts.conf"
                    if not self._is_vhosts_enabled():
                        self._enable_vhosts_in_httpd_conf()

                    try:
                        with open(vhosts_file, "a", encoding="utf-8") as vf:
                            vf.write(ssl_stanza)
                    except PermissionError:
                        tmp_vh = "/tmp/vhost_ssl.tmp"
                        curr = ""
                        if os.path.isfile(vhosts_file):
                            with open(vhosts_file, "r", encoding="utf-8", errors="replace") as f:
                                curr = f.read()
                        with open(tmp_vh, "w", encoding="utf-8") as f:
                            f.write(curr + ssl_stanza)
                        subprocess.run(["pkexec", "cp", tmp_vh, vhosts_file], check=True, timeout=15)
                        try:
                            os.remove(tmp_vh)
                        except Exception:
                            pass

                trust_cmd = f"sudo cp {target_crt} /usr/local/share/ca-certificates/{domain}.crt && sudo update-ca-certificates"
                info_text = f"✔ Certificado generado en:\n  {target_crt}\n  {target_key}\n\nPara confiar en este certificado en Linux Mint:\n{trust_cmd}"
                info_box.configure(text=info_text)
                info_box.grid()

                self.send_notification(f"Certificado SSL generado para {domain}")
                write_log(f"Certificado SSL para {domain} generado exitosamente.")
                
                if messagebox.askyesno("Éxito", f"Certificado para '{domain}' generado.\n\n¿Deseas reiniciar Apache ahora para cargar SSL?"):
                    self.run_service("restart", "apache")

            except Exception as ex:
                write_log(f"Error generando certificado SSL: {ex}")
                messagebox.showerror("Error", f"No se pudo generar el certificado:\n{ex}")

        btn_box = tk.Frame(win, bg=t["bg"])
        btn_box.pack(pady=10)

        tk.Button(btn_box, text="🔐 Generar Certificado SSL", bg=t["btn_start"], fg="white",
                  font=("Helvetica", 9, "bold"), command=generate_ssl).pack(side="left", padx=5)
        tk.Button(btn_box, text="Cerrar", bg=t["bg_button"], fg=t["fg"],
                  font=("Helvetica", 9), command=win.destroy).pack(side="left", padx=5)

    def _collect_resource_telemetry(self):
        """Recolecta métricas en vivo de CPU, RAM RSS y conexiones de XAMPP."""
        data = {
            "apache": {"count": 0, "rss_mb": 0.0, "cpu_pct": 0.0},
            "mysql": {"count": 0, "rss_mb": 0.0, "cpu_pct": 0.0, "threads": "N/D", "uptime": "N/D", "queries": "N/D"},
            "proftpd": {"count": 0, "rss_mb": 0.0, "cpu_pct": 0.0},
            "total_rss_mb": 0.0
        }

        try:
            res = subprocess.run(["ps", "-e", "-o", "pid,rss,%cpu,comm"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                for line in res.stdout.splitlines()[1:]:
                    parts = line.strip().split(None, 3)
                    if len(parts) >= 4:
                        try:
                            pid = int(parts[0])
                            rss_kb = float(parts[1])
                            cpu_val = float(parts[2])
                            comm = parts[3].lower()

                            if not _is_lampp_pid(pid):
                                continue

                            rss_mb = rss_kb / 1024.0

                            if any(k in comm for k in ("httpd", "apache2")):
                                data["apache"]["count"] += 1
                                data["apache"]["rss_mb"] += rss_mb
                                data["apache"]["cpu_pct"] += cpu_val
                            elif "mysqld" in comm:
                                data["mysql"]["count"] += 1
                                data["mysql"]["rss_mb"] += rss_mb
                                data["mysql"]["cpu_pct"] += cpu_val
                            elif "proftpd" in comm:
                                data["proftpd"]["count"] += 1
                                data["proftpd"]["rss_mb"] += rss_mb
                                data["proftpd"]["cpu_pct"] += cpu_val
                        except (ValueError, IndexError):
                            continue
        except Exception as e:
            write_log(f"Error recolectando telemetría de procesos: {e}")

        if self._port_open("127.0.0.1", 3306) and data["mysql"]["count"] > 0:
            mysql_bin = self._get_mysql_bin("mysql")
            try:
                cmd = [mysql_bin, "-u", "root", "-e", "SHOW STATUS WHERE Variable_name IN ('Threads_connected','Uptime','Queries');"]
                res_m = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
                if res_m.returncode == 0:
                    for line in res_m.stdout.splitlines():
                        if "Threads_connected" in line:
                            data["mysql"]["threads"] = line.split()[-1]
                        elif "Uptime" in line:
                            secs = int(line.split()[-1])
                            h = secs // 3600
                            m = (secs % 3600) // 60
                            s = secs % 60
                            data["mysql"]["uptime"] = f"{h}h {m}m {s}s"
                        elif "Queries" in line:
                            data["mysql"]["queries"] = line.split()[-1]
            except Exception:
                pass

        data["total_rss_mb"] = data["apache"]["rss_mb"] + data["mysql"]["rss_mb"] + data["proftpd"]["rss_mb"]
        return data

    def show_performance_monitor(self):
        """Muestra el monitor de recursos y telemetría en tiempo real de XAMPP."""
        t = THEMES[self.current_theme]
        win = tk.Toplevel(self.root)
        win.title("Monitor de Rendimiento en Vivo (CPU / RAM)")
        win.geometry("520x460")
        win.resizable(False, False)
        win.transient(self.root)
        win.configure(bg=t["bg"])

        tk.Label(win, text="Monitor de Recursos de XAMPP", font=("Helvetica", 12, "bold"),
                 bg=t["bg"], fg=t["fg_label"]).pack(pady=(12, 6))

        container = tk.Frame(win, bg=t["bg"], padx=15)
        container.pack(fill="both", expand=True)

        card_ap = tk.Frame(container, bg=t["bg_secondary"], padx=10, pady=8, highlightbackground="#313244", highlightthickness=1)
        card_ap.pack(fill="x", pady=4)
        lbl_ap_title = tk.Label(card_ap, text="🌐 Servidor Apache", font=("Helvetica", 10, "bold"), bg=t["bg_secondary"], fg=t["fg_label"])
        lbl_ap_title.pack(anchor="w")
        lbl_ap_stats = tk.Label(card_ap, text="Cargando telemetría...", font=("Helvetica", 9), bg=t["bg_secondary"], fg=t["fg"], justify="left")
        lbl_ap_stats.pack(anchor="w", pady=(2, 0))

        card_my = tk.Frame(container, bg=t["bg_secondary"], padx=10, pady=8, highlightbackground="#313244", highlightthickness=1)
        card_my.pack(fill="x", pady=4)
        lbl_my_title = tk.Label(card_my, text="🐬 Servidor MySQL / MariaDB", font=("Helvetica", 10, "bold"), bg=t["bg_secondary"], fg=t["fg_label"])
        lbl_my_title.pack(anchor="w")
        lbl_my_stats = tk.Label(card_my, text="Cargando telemetría...", font=("Helvetica", 9), bg=t["bg_secondary"], fg=t["fg"], justify="left")
        lbl_my_stats.pack(anchor="w", pady=(2, 0))

        card_ftp = tk.Frame(container, bg=t["bg_secondary"], padx=10, pady=8, highlightbackground="#313244", highlightthickness=1)
        card_ftp.pack(fill="x", pady=4)
        lbl_ftp_title = tk.Label(card_ftp, text="📁 Servidor ProFTPD", font=("Helvetica", 10, "bold"), bg=t["bg_secondary"], fg=t["fg_label"])
        lbl_ftp_title.pack(anchor="w")
        lbl_ftp_stats = tk.Label(card_ftp, text="Cargando telemetría...", font=("Helvetica", 9), bg=t["bg_secondary"], fg=t["fg"], justify="left")
        lbl_ftp_stats.pack(anchor="w", pady=(2, 0))

        tot_frame = tk.Frame(container, bg=t["bg"], pady=6)
        tot_frame.pack(fill="x", pady=4)
        lbl_total = tk.Label(tot_frame, text="Memoria RAM total ocupada por XAMPP: 0.0 MB", font=("Helvetica", 9, "bold"), bg=t["bg"], fg=t["fg"])
        lbl_total.pack(anchor="w")

        is_active_ref = [True]

        def update_metrics():
            if not is_active_ref[0] or not win.winfo_exists():
                return
            data = self._collect_resource_telemetry()

            ap = data["apache"]
            txt_ap = f"Procesos (Workers): {ap['count']}  |  RAM: {ap['rss_mb']:.1f} MB  |  CPU: {ap['cpu_pct']:.1f}%"
            lbl_ap_stats.configure(text=txt_ap)

            my = data["mysql"]
            txt_my = f"Procesos: {my['count']}  |  RAM: {my['rss_mb']:.1f} MB  |  CPU: {my['cpu_pct']:.1f}%\nConexiones activas: {my['threads']}  |  Consultas: {my['queries']}  |  Uptime: {my['uptime']}"
            lbl_my_stats.configure(text=txt_my)

            ftp = data["proftpd"]
            txt_ftp = f"Procesos: {ftp['count']}  |  RAM: {ftp['rss_mb']:.1f} MB  |  CPU: {ftp['cpu_pct']:.1f}%"
            lbl_ftp_stats.configure(text=txt_ftp)

            lbl_total.configure(text=f"Memoria RAM total ocupada por XAMPP: {data['total_rss_mb']:.1f} MB")

            if var_auto.get():
                win.after(2000, update_metrics)

        def on_close():
            is_active_ref[0] = False
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", on_close)

        btn_bar = tk.Frame(win, bg=t["bg"])
        btn_bar.pack(fill="x", padx=15, pady=(6, 12))

        var_auto = tk.BooleanVar(value=True)
        chk_auto = tk.Checkbutton(btn_bar, text="Actualizar en vivo (cada 2s)", variable=var_auto,
                                  bg=t["bg"], fg=t["fg"], selectcolor=t["bg_secondary"],
                                  command=lambda: update_metrics() if var_auto.get() else None)
        chk_auto.pack(side="left")

        tk.Button(btn_bar, text="🔄 Actualizar Ahora", bg=t["btn_start"], fg="white",
                  font=("Helvetica", 8, "bold"), command=update_metrics).pack(side="right", padx=4)
        tk.Button(btn_bar, text="Cerrar", bg=t["bg_button"], fg=t["fg"],
                  font=("Helvetica", 8), command=on_close).pack(side="right", padx=4)

        update_metrics()

    SNAPSHOTS_DIR = os.path.expanduser("~/.local/share/xampp-gui/snapshots")

    def _list_snapshots(self):
        """Lista las instantáneas disponibles ordenadas por fecha reciente."""
        if not os.path.isdir(self.SNAPSHOTS_DIR):
            return []
        snaps = []
        try:
            for entry in os.scandir(self.SNAPSHOTS_DIR):
                if entry.is_dir():
                    manifest_path = os.path.join(entry.path, "manifest.json")
                    if os.path.isfile(manifest_path):
                        try:
                            with open(manifest_path, "r", encoding="utf-8") as f:
                                meta = json.load(f)
                            meta["path"] = entry.path
                            snaps.append(meta)
                        except Exception:
                            pass
        except Exception as e:
            write_log(f"Error listando instantáneas: {e}")
        snaps.sort(key=lambda s: s.get("created_at", ""), reverse=True)
        return snaps

    def create_snapshot(self, description="Punto de control"):
        """Crea un snapshot completo de bases de datos y configuraciones."""
        os.makedirs(self.SNAPSHOTS_DIR, exist_ok=True)
        snap_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        target_dir = os.path.join(self.SNAPSHOTS_DIR, snap_id)
        os.makedirs(target_dir, exist_ok=True)
        cfg_dir = os.path.join(target_dir, "configs")
        os.makedirs(cfg_dir, exist_ok=True)

        dump_path = os.path.join(target_dir, "databases.sql")
        dump_bin = self._get_mysql_bin("mysqldump")
        has_db_dump = False

        if self._port_open("127.0.0.1", 3306):
            try:
                cmd = [
                    dump_bin, "-u", "root",
                    "--all-databases",
                    "--single-transaction",
                    "--routines",
                    "--triggers",
                    "--default-character-set=utf8mb4"
                ]
                with open(dump_path, "w", encoding="utf-8") as out:
                    res = subprocess.run(cmd, stdout=out, stderr=subprocess.PIPE, text=True, timeout=120)
                if res.returncode == 0:
                    has_db_dump = True
            except Exception as e:
                write_log(f"Error volcando bases de datos para snapshot: {e}")

        key_configs = [
            "/opt/lampp/etc/php.ini",
            "/opt/lampp/etc/httpd.conf",
            "/opt/lampp/etc/extra/httpd-vhosts.conf",
            "/opt/lampp/etc/extra/httpd-ssl.conf",
            "/opt/lampp/etc/my.cnf"
        ]
        backed_cfgs = []
        for cfg in key_configs:
            if os.path.isfile(cfg):
                dst = os.path.join(cfg_dir, os.path.basename(cfg))
                try:
                    shutil.copy2(cfg, dst)
                    backed_cfgs.append(os.path.basename(cfg))
                except Exception:
                    pass

        total_bytes = 0
        for root_d, _, files in os.walk(target_dir):
            for fl in files:
                total_bytes += os.path.getsize(os.path.join(root_d, fl))
        size_mb = total_bytes / (1024.0 * 1024.0)

        manifest = {
            "id": snap_id,
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "description": description,
            "has_databases": has_db_dump,
            "configs": backed_cfgs,
            "size_mb": round(size_mb, 2)
        }

        with open(os.path.join(target_dir, "manifest.json"), "w", encoding="utf-8") as mf:
            json.dump(manifest, mf, indent=2)

        write_log(f"Snapshot '{snap_id}' creado con éxito ({size_mb:.2f} MB).")
        return manifest

    def restore_snapshot(self, snap_id):
        """Restaura bases de datos y archivos de configuración desde un snapshot."""
        target_dir = os.path.join(self.SNAPSHOTS_DIR, snap_id)
        manifest_path = os.path.join(target_dir, "manifest.json")
        if not os.path.isfile(manifest_path):
            raise FileNotFoundError(f"No se encontró manifest en {target_dir}")

        with open(manifest_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        cfg_dir = os.path.join(target_dir, "configs")
        cfg_map = {
            "php.ini": "/opt/lampp/etc/php.ini",
            "httpd.conf": "/opt/lampp/etc/httpd.conf",
            "httpd-vhosts.conf": "/opt/lampp/etc/extra/httpd-vhosts.conf",
            "httpd-ssl.conf": "/opt/lampp/etc/extra/httpd-ssl.conf",
            "my.cnf": "/opt/lampp/etc/my.cnf"
        }

        for cfg_name, dst_path in cfg_map.items():
            src_cfg = os.path.join(cfg_dir, cfg_name)
            if os.path.isfile(src_cfg):
                try:
                    shutil.copy2(src_cfg, dst_path)
                except PermissionError:
                    subprocess.run(["pkexec", "cp", src_cfg, dst_path], check=True, timeout=10)

        dump_path = os.path.join(target_dir, "databases.sql")
        if meta.get("has_databases") and os.path.isfile(dump_path) and self._port_open("127.0.0.1", 3306):
            mysql_bin = self._get_mysql_bin("mysql")
            with open(dump_path, "r", encoding="utf-8", errors="replace") as in_f:
                subprocess.run([mysql_bin, "-u", "root"], stdin=in_f, check=True, timeout=180)

        write_log(f"Snapshot '{snap_id}' restaurado exitosamente.")
        return True

    def delete_snapshot(self, snap_id):
        """Elimina una carpeta de snapshot."""
        target_dir = os.path.join(self.SNAPSHOTS_DIR, snap_id)
        if os.path.isdir(target_dir):
            shutil.rmtree(target_dir)
            write_log(f"Snapshot '{snap_id}' eliminado.")
            return True
        return False

    def show_snapshots_manager(self):
        """Muestra el administrador de puntos de restauración y snapshots."""
        t = THEMES[self.current_theme]
        win = tk.Toplevel(self.root)
        win.title("Puntos de Restauración y Snapshots")
        win.geometry("620x440")
        win.resizable(False, False)
        win.transient(self.root)
        win.configure(bg=t["bg"])

        tk.Label(win, text="Puntos de Restauración (Instantáneas de XAMPP)", font=("Helvetica", 12, "bold"),
                 bg=t["bg"], fg=t["fg_label"]).pack(pady=(12, 6))

        tree_frame = tk.Frame(win, bg=t["bg"])
        tree_frame.pack(fill="both", expand=True, padx=12, pady=6)

        cols = ("Fecha", "Descripción", "BD", "Tamaño")
        tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=10)
        tree.heading("Fecha", text="Fecha y Hora")
        tree.heading("Descripción", text="Descripción / Motivo")
        tree.heading("BD", text="Bases de Datos")
        tree.heading("Tamaño", text="Tamaño")

        tree.column("Fecha", width=140)
        tree.column("Descripción", width=260)
        tree.column("BD", width=90, anchor="center")
        tree.column("Tamaño", width=80, anchor="center")

        tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        snapshots_cache = []

        def refresh():
            nonlocal snapshots_cache
            for item in tree.get_children():
                tree.delete(item)
            snapshots_cache = self._list_snapshots()
            for s in snapshots_cache:
                bd_txt = "Sí (Todas)" if s.get("has_databases") else "No"
                tree.insert("", "end", iid=s["id"], values=(
                    s.get("created_at", ""),
                    s.get("description", ""),
                    bd_txt,
                    f"{s.get('size_mb', 0)} MB"
                ))

        refresh()

        btn_bar = tk.Frame(win, bg=t["bg"])
        btn_bar.pack(fill="x", padx=12, pady=(6, 12))

        def on_create():
            from tkinter import simpledialog
            desc = simpledialog.askstring("Nuevo Snapshot", "Motivo o descripción de la instantánea:",
                                          initialvalue="Antes de actualizar", parent=win)
            if desc:
                self.show_progress()
                def worker():
                    try:
                        self.create_snapshot(desc.strip())
                        self.send_notification("Instantánea creada con éxito")
                        self.safe_after(0, lambda: (refresh(), messagebox.showinfo("Éxito", "Instantánea guardada correctamente.")))
                    except Exception as ex:
                        write_log(f"Error creando snapshot: {ex}")
                        self.safe_after(0, lambda: messagebox.showerror("Error", f"No se pudo crear snapshot:\n{ex}"))
                    finally:
                        self.safe_after(0, self.hide_progress)

                threading.Thread(target=worker, daemon=True).start()

        def on_restore():
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("Seleccionar", "Selecciona una instantánea para restaurar.")
                return
            snap_id = sel[0]
            if messagebox.askyesno("Confirmar Restauración",
                                   f"¿Estás seguro de restaurar el snapshot '{snap_id}'?\n\n"
                                   "Esto reemplazará las bases de datos y archivos de configuración actuales."):
                self.show_progress()
                def worker():
                    try:
                        self.restore_snapshot(snap_id)
                        self.send_notification("Snapshot restaurado")
                        self.safe_after(0, lambda: messagebox.showinfo("Éxito", f"Snapshot '{snap_id}' restaurado correctamente."))
                        if messagebox.askyesno("Reiniciar", "¿Deseas reiniciar los servicios ahora?"):
                            self.run_service("restart", "all")
                    except Exception as ex:
                        write_log(f"Error restaurando snapshot: {ex}")
                        self.safe_after(0, lambda: messagebox.showerror("Error", f"Fallo al restaurar:\n{ex}"))
                    finally:
                        self.safe_after(0, self.hide_progress)

                threading.Thread(target=worker, daemon=True).start()

        def on_delete():
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("Seleccionar", "Selecciona una instantánea para eliminar.")
                return
            snap_id = sel[0]
            if messagebox.askyesno("Eliminar", f"¿Eliminar la instantánea '{snap_id}' definitivamente?"):
                self.delete_snapshot(snap_id)
                refresh()

        tk.Button(btn_bar, text="➕ Crear Instantánea...", bg=t["btn_start"], fg="white",
                  font=("Helvetica", 9, "bold"), command=on_create).pack(side="left", padx=3)
        tk.Button(btn_bar, text="🔄 Restaurar Instantánea", bg=t["btn_restart"], fg="white",
                  font=("Helvetica", 9, "bold"), command=on_restore).pack(side="left", padx=3)
        tk.Button(btn_bar, text="🗑 Eliminar", bg=t["btn_stop"], fg="white",
                  font=("Helvetica", 9), command=on_delete).pack(side="left", padx=3)
        tk.Button(btn_bar, text="Cerrar", bg=t["bg_button"], fg=t["fg"],
                  font=("Helvetica", 9), command=win.destroy).pack(side="right", padx=3)

    def _scan_php_environments(self):
        """Escanea todos los binarios PHP disponibles en el sistema Linux."""
        candidates = ["/opt/lampp/bin/php", "/usr/bin/php"] + sorted(glob.glob("/usr/bin/php[5-9].[0-9]"))
        seen = set()
        environments = []

        for p in candidates:
            if os.path.isfile(p):
                try:
                    real = os.path.realpath(p)
                    if real in seen:
                        continue
                    seen.add(real)

                    res_v = subprocess.run([p, "-v"], capture_output=True, text=True, timeout=3)
                    first_line = res_v.stdout.splitlines()[0] if res_v.stdout else "PHP Desconocido"
                    m_v = re.search(r'PHP\s+([0-9]+\.[0-9]+\.[0-9]+)', first_line)
                    version = m_v.group(1) if m_v else "N/D"

                    res_m = subprocess.run([p, "-m"], capture_output=True, text=True, timeout=3)
                    modules_count = len([m for m in res_m.stdout.splitlines() if m.strip()]) if res_m.returncode == 0 else 0

                    is_xampp = "/opt/lampp" in real
                    tag = "XAMPP LAMPP" if is_xampp else "Sistema Linux Mint"

                    environments.append({
                        "path": p,
                        "real_path": real,
                        "version": version,
                        "title": first_line,
                        "modules_count": modules_count,
                        "tag": tag,
                        "is_xampp": is_xampp
                    })
                except Exception as e:
                    write_log(f"Error analizando binario PHP {p}: {e}")

        return environments

    def open_terminal_with_php(self, php_bin):
        """Lanza un emulador de terminal con el entorno PATH preconfigurado para ese PHP."""
        bin_dir = os.path.dirname(os.path.realpath(php_bin))
        term_bin = self.find_terminal()
        if not term_bin:
            messagebox.showerror("Error", "No se detectó ningún emulador de terminal en el sistema.")
            return

        cmd_payload = (
            f"export PATH=\"{bin_dir}:$PATH\"; "
            f"echo -e '\\e[1;34m=========================================================\\e[0m'; "
            f"echo -e '\\e[1;32m✔ Entorno PHP activado:\\e[0m $({php_bin} -v | head -n1)'; "
            f"echo -e '\\e[1;36m✔ Binario activo:\\e[0m $(which php)'; "
            f"echo -e '\\e[1;34m=========================================================\\e[0m'; "
            f"exec bash"
        )

        try:
            if any(t in term_bin for t in ("gnome-terminal", "mate-terminal", "xfce4-terminal", "tilix")):
                subprocess.Popen([term_bin, "--", "bash", "-c", cmd_payload], cwd=HTDOCS_PATH)
            elif "konsole" in term_bin:
                subprocess.Popen([term_bin, "-e", "bash", "-c", cmd_payload], cwd=HTDOCS_PATH)
            elif any(t in term_bin for t in ("alacritty", "kitty")):
                subprocess.Popen([term_bin, "-e", "bash", "-c", cmd_payload], cwd=HTDOCS_PATH)
            else:
                subprocess.Popen([term_bin, "-e", f"bash -c '{cmd_payload}'"], cwd=HTDOCS_PATH)
            self.send_notification(f"Terminal abierta con PHP {os.path.basename(php_bin)}")
        except Exception as e:
            write_log(f"Error lanzando terminal con PHP {php_bin}: {e}")
            messagebox.showerror("Error", f"No se pudo abrir la terminal:\n{e}")

    def show_php_environments_dialog(self):
        """Muestra los entornos de PHP detectados en Linux Mint y permite lanzar terminales."""
        t = THEMES[self.current_theme]
        win = tk.Toplevel(self.root)
        win.title("Entornos de PHP del Sistema (CLI)")
        win.geometry("540x440")
        win.resizable(False, False)
        win.transient(self.root)
        win.configure(bg=t["bg"])

        tk.Label(win, text="Versiones y Entornos de PHP Disponibles", font=("Helvetica", 12, "bold"),
                 bg=t["bg"], fg=t["fg_label"]).pack(pady=(12, 6))

        frame = tk.Frame(win, bg=t["bg"], padx=15)
        frame.pack(fill="both", expand=True)

        envs = self._scan_php_environments()
        if not envs:
            tk.Label(frame, text="No se detectaron binarios de PHP.", bg=t["bg"], fg=t["fg"]).pack(pady=20)
        else:
            for env in envs:
                card = tk.Frame(frame, bg=t["bg_secondary"], padx=10, pady=8, highlightbackground="#313244", highlightthickness=1)
                card.pack(fill="x", pady=4)

                badge_color = t["fg_active"] if env["is_xampp"] else t["fg_label"]
                tk.Label(card, text=f"[{env['tag']}]", font=("Helvetica", 8, "bold"),
                         bg=t["bg_secondary"], fg=badge_color).pack(anchor="w")

                tk.Label(card, text=f"PHP v{env['version']} ({env['modules_count']} módulos cargados)",
                         font=("Helvetica", 10, "bold"), bg=t["bg_secondary"], fg=t["fg"]).pack(anchor="w")

                tk.Label(card, text=env["path"], font=("Monospace", 8),
                         bg=t["bg_secondary"], fg="#888888").pack(anchor="w", pady=(0, 4))

                tk.Button(card, text="💻 Abrir Terminal con este PHP", bg=t["bg_button"], fg=t["fg"],
                          font=("Helvetica", 8, "bold"), command=lambda b=env["path"]: self.open_terminal_with_php(b)).pack(anchor="w")

        tk.Button(win, text="Cerrar", bg=t["bg_button"], fg=t["fg"],
                  font=("Helvetica", 9), command=win.destroy).pack(pady=8)

    # =========================================================================
    # v2.6: Benchmark (ab), Túnel SSH Público, Live Log Tail y Editor .htaccess
    # =========================================================================

    def show_benchmark_dialog(self):
        """Herramienta de benchmark y pruebas de carga con ApacheBench (ab)."""
        t = THEMES[self.current_theme]
        win = tk.Toplevel(self.root)
        win.title("Benchmark de Servidor (ApacheBench)")
        win.geometry("560x540")
        win.resizable(False, False)
        win.transient(self.root)
        win.configure(bg=t["bg"])

        tk.Label(win, text="Auditoría de Rendimiento con ApacheBench", font=("Helvetica", 12, "bold"),
                 bg=t["bg"], fg=t["fg_label"]).pack(pady=(12, 6))

        ab_bin = "/opt/lampp/bin/ab"
        if not os.path.isfile(ab_bin):
            ab_bin = shutil.which("ab") or ab_bin

        frame_top = tk.Frame(win, bg=t["bg"], padx=15)
        frame_top.pack(fill="x")

        tk.Label(frame_top, text="URL objetivo a evaluar:", font=("Helvetica", 9),
                 bg=t["bg"], fg=t["fg"]).grid(row=0, column=0, sticky="w", pady=2)
        
        default_url = "http://localhost/"
        selected_proj = self.project_var.get().strip() if hasattr(self, "project_var") else ""
        if selected_proj:
            default_url = f"http://localhost/{selected_proj}/"

        ent_url = tk.Entry(frame_top, width=44, font=("Helvetica", 9))
        ent_url.grid(row=1, column=0, columnspan=3, sticky="we", pady=(0, 6))
        ent_url.insert(0, default_url)

        tk.Label(frame_top, text="Total Peticiones (-n):", font=("Helvetica", 9),
                 bg=t["bg"], fg=t["fg"]).grid(row=2, column=0, sticky="w", pady=2)
        ent_n = tk.Entry(frame_top, width=12, font=("Helvetica", 9))
        ent_n.grid(row=3, column=0, sticky="w", pady=(0, 6))
        ent_n.insert(0, "100")

        tk.Label(frame_top, text="Concurrencia (-c):", font=("Helvetica", 9),
                 bg=t["bg"], fg=t["fg"]).grid(row=2, column=1, sticky="w", pady=2)
        ent_c = tk.Entry(frame_top, width=12, font=("Helvetica", 9))
        ent_c.grid(row=3, column=1, sticky="w", pady=(0, 6))
        ent_c.insert(0, "10")

        res_card = tk.Frame(win, bg=t["bg_secondary"], padx=12, pady=10, highlightbackground="#313244", highlightthickness=1)
        res_card.pack(fill="x", padx=15, pady=8)

        lbl_summary = tk.Label(res_card, text="Configura los parámetros y pulsa 'Ejecutar Benchmark'.",
                               font=("Helvetica", 9), bg=t["bg_secondary"], fg=t["fg"], justify="left")
        lbl_summary.pack(anchor="w")

        tk.Label(win, text="Reporte Detallado de ApacheBench:", font=("Helvetica", 9, "bold"),
                 bg=t["bg"], fg=t["fg_label"]).pack(anchor="w", padx=15, pady=(4, 2))

        txt_report = scrolledtext.ScrolledText(win, height=10, font=("Monospace", 8),
                                              bg=t["bg_secondary"], fg=t["fg"])
        txt_report.pack(fill="both", expand=True, padx=15, pady=(0, 8))

        def run_bench():
            url = ent_url.get().strip()
            num_req = ent_n.get().strip() or "100"
            concurr = ent_c.get().strip() or "10"

            if not url.startswith("http://") and not url.startswith("https://"):
                messagebox.showerror("URL inválida", "La URL debe comenzar con http:// o https://")
                return

            if not os.path.isfile(ab_bin):
                messagebox.showerror("ab no encontrado", f"No se encontró ApacheBench en {ab_bin}")
                return

            btn_run.configure(state="disabled", text="⏳ Evaluando...")
            lbl_summary.configure(text=f"Ejecutando {num_req} peticiones concurrentes a {url}...", fg=t["fg_label"])
            txt_report.delete("1.0", tk.END)

            def worker():
                try:
                    cmd = [ab_bin, "-n", str(num_req), "-c", str(concurr), url]
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                    out = res.stdout + res.stderr

                    m_rps = re.search(r'Requests per second:\s+([0-9.]+)', out)
                    m_lat = re.search(r'Time per request:\s+([0-9.]+)\s+\[ms\]\s+\(mean\)', out)
                    m_rate = re.search(r'Transfer rate:\s+([0-9.]+)\s+\[Kbytes/sec\]', out)
                    m_fail = re.search(r'Failed requests:\s+([0-9]+)', out)

                    rps = m_rps.group(1) if m_rps else "N/D"
                    lat = m_lat.group(1) if m_lat else "N/D"
                    rate = m_rate.group(1) if m_rate else "N/D"
                    fail = m_fail.group(1) if m_fail else "0"

                    summary_txt = (
                        f"🚀 Rendimiento: {rps} peticiones/seg (RPS)\n"
                        f"⏱ Latencia Media: {lat} ms\n"
                        f"📦 Tasa de Transferencia: {rate} KB/s\n"
                        f"❌ Peticiones Fallidas: {fail}"
                    )

                    def update_ui():
                        lbl_summary.configure(text=summary_txt, fg=t["fg_active"] if fail == "0" else t.get("fg_conflict", "#fab387"))
                        txt_report.insert(tk.END, out)
                        btn_run.configure(state="normal", text="⚡ Ejecutar Benchmark")
                        self.send_notification("Benchmark completado con éxito")
                        write_log(f"Benchmark ejecutado en {url}: {rps} RPS")

                    self.safe_after(0, update_ui)

                except Exception as ex:
                    self.safe_after(0, lambda: (
                        lbl_summary.configure(text=f"Error en benchmark: {ex}", fg=t["fg_inactive"]),
                        btn_run.configure(state="normal", text="⚡ Ejecutar Benchmark"),
                        write_log(f"Error ejecutando ab: {ex}")
                    ))

            threading.Thread(target=worker, daemon=True).start()

        btn_bar = tk.Frame(win, bg=t["bg"])
        btn_bar.pack(fill="x", padx=15, pady=(0, 10))

        btn_run = tk.Button(btn_bar, text="⚡ Ejecutar Benchmark", bg=t["btn_start"], fg="white",
                            font=("Helvetica", 9, "bold"), command=run_bench)
        btn_run.pack(side="left", padx=3)

        def copy_rep():
            win.clipboard_clear()
            win.clipboard_append(txt_report.get("1.0", tk.END))
            self.send_notification("Reporte copiado al portapapeles")

        tk.Button(btn_bar, text="📋 Copiar Reporte", bg=t["bg_button"], fg=t["fg"],
                  font=("Helvetica", 9), command=copy_rep).pack(side="left", padx=3)
        tk.Button(btn_bar, text="Cerrar", bg=t["bg_button"], fg=t["fg"],
                  font=("Helvetica", 9), command=win.destroy).pack(side="right", padx=3)

    def show_tunnel_dialog(self):
        """Expone el servidor local a Internet mediante un túnel público seguro (SSH)."""
        t = THEMES[self.current_theme]
        win = tk.Toplevel(self.root)
        win.title("Compartir Proyecto en Internet (Túnel Público)")
        win.geometry("520x400")
        win.resizable(False, False)
        win.transient(self.root)
        win.configure(bg=t["bg"])

        tk.Label(win, text="Compartir Servidor Local en Internet", font=("Helvetica", 12, "bold"),
                 bg=t["bg"], fg=t["fg_label"]).pack(pady=(12, 6))

        card = tk.Frame(win, bg=t["bg_secondary"], padx=15, pady=12, highlightbackground="#313244", highlightthickness=1)
        card.pack(fill="both", expand=True, padx=15, pady=8)

        tk.Label(card, text="Permite probar webhooks (Stripe/PayPal), APIs externas y mostrar avances\n"
                            "a clientes conectando tu localhost a una URL pública HTTPS temporal.",
                 font=("Helvetica", 9), bg=t["bg_secondary"], fg=t["fg"], justify="left").pack(anchor="w", pady=(0, 10))

        lbl_status = tk.Label(card, text="● Estado: Desconectado", font=("Helvetica", 10, "bold"),
                              bg=t["bg_secondary"], fg=t["fg_inactive"])
        lbl_status.pack(anchor="w", pady=4)

        ent_url = tk.Entry(card, width=42, font=("Monospace", 9))
        ent_url.pack(fill="x", pady=6)
        ent_url.insert(0, "Inicia el túnel para obtener la URL pública...")
        ent_url.configure(state="readonly")

        txt_log = scrolledtext.ScrolledText(card, height=5, font=("Monospace", 8),
                                            bg=t["bg"], fg=t["fg"])
        txt_log.pack(fill="both", expand=True, pady=6)

        tunnel_state = getattr(self, "_tunnel_state", {"proc": None, "url": ""})
        self._tunnel_state = tunnel_state

        def start_tunnel():
            ssh_bin = shutil.which("ssh") or "/usr/bin/ssh"
            if not os.path.isfile(ssh_bin):
                messagebox.showerror("Error", "No se encontró el comando 'ssh' en el sistema.")
                return

            btn_start.configure(state="disabled")
            btn_stop.configure(state="normal")
            lbl_status.configure(text="● Conectando túnel...", fg=t.get("fg_conflict", "#fab387"))

            def worker():
                try:
                    cmd = [
                        ssh_bin, "-R", "80:localhost:80",
                        "-o", "StrictHostKeyChecking=no",
                        "-o", "ServerAliveInterval=60",
                        "nokey@localhost.run"
                    ]
                    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                    tunnel_state["proc"] = proc

                    for line in iter(proc.stdout.readline, ''):
                        txt_log.insert(tk.END, line)
                        txt_log.see(tk.END)

                        m = re.search(r'(https://[a-zA-Z0-9.-]+\.lhr\.life|https://[a-zA-Z0-9.-]+\.localhost\.run)', line)
                        if m and not tunnel_state.get("url"):
                            found_url = m.group(1)
                            tunnel_state["url"] = found_url

                            def on_connected(u=found_url):
                                lbl_status.configure(text="● Conectado (Túnel activo)", fg=t["fg_active"])
                                ent_url.configure(state="normal")
                                ent_url.delete(0, tk.END)
                                ent_url.insert(0, u)
                                ent_url.configure(state="readonly")
                                btn_copy.configure(state="normal")
                                btn_open.configure(state="normal")
                                self.send_notification("Túnel público activo: " + u)
                                write_log(f"Túnel público activo en {u}")

                            self.safe_after(0, on_connected)

                    proc.wait()
                except Exception as ex:
                    write_log(f"Error en túnel SSH: {ex}")
                finally:
                    def on_finish():
                        tunnel_state["proc"] = None
                        tunnel_state["url"] = ""
                        lbl_status.configure(text="● Estado: Desconectado", fg=t["fg_inactive"])
                        btn_start.configure(state="normal")
                        btn_stop.configure(state="disabled")
                        btn_copy.configure(state="disabled")
                        btn_open.configure(state="disabled")
                    self.safe_after(0, on_finish)

            threading.Thread(target=worker, daemon=True).start()

        def stop_tunnel():
            if tunnel_state.get("proc"):
                try:
                    tunnel_state["proc"].terminate()
                except Exception:
                    pass
                tunnel_state["proc"] = None
                tunnel_state["url"] = ""
                lbl_status.configure(text="● Estado: Desconectado", fg=t["fg_inactive"])
                btn_start.configure(state="normal")
                btn_stop.configure(state="disabled")

        def copy_url():
            u = tunnel_state.get("url")
            if u:
                win.clipboard_clear()
                win.clipboard_append(u)
                self.send_notification("URL del túnel copiada al portapapeles")

        def open_url():
            u = tunnel_state.get("url")
            if u:
                webbrowser.open(u)

        btn_bar = tk.Frame(win, bg=t["bg"])
        btn_bar.pack(fill="x", padx=15, pady=(4, 12))

        btn_start = tk.Button(btn_bar, text="▶ Iniciar Túnel", bg=t["btn_start"], fg="white",
                              font=("Helvetica", 9, "bold"), command=start_tunnel)
        btn_start.pack(side="left", padx=3)

        btn_stop = tk.Button(btn_bar, text="⏹ Detener Túnel", bg=t["btn_stop"], fg="white",
                             font=("Helvetica", 9), state="disabled", command=stop_tunnel)
        btn_stop.pack(side="left", padx=3)

        btn_copy = tk.Button(btn_bar, text="📋 Copiar URL", bg=t["bg_button"], fg=t["fg"],
                             font=("Helvetica", 8), state="disabled", command=copy_url)
        btn_copy.pack(side="left", padx=3)

        btn_open = tk.Button(btn_bar, text="🌐 Abrir", bg=t["bg_button"], fg=t["fg"],
                             font=("Helvetica", 8), state="disabled", command=open_url)
        btn_open.pack(side="left", padx=3)

        tk.Button(btn_bar, text="Cerrar", bg=t["bg_button"], fg=t["fg"],
                  font=("Helvetica", 9), command=win.destroy).pack(side="right", padx=3)

    def show_live_log_tail(self):
        """Monitor de streaming de logs de Apache y PHP en tiempo real (Live Tail)."""
        t = THEMES[self.current_theme]
        win = tk.Toplevel(self.root)
        win.title("Monitor en Vivo de Logs (Live Tail)")
        win.geometry("680x500")
        win.minsize(580, 400)
        win.transient(self.root)
        win.configure(bg=t["bg"])

        top_bar = tk.Frame(win, bg=t["bg"], padx=12, pady=8)
        top_bar.pack(fill="x")

        tk.Label(top_bar, text="Archivo de log:", font=("Helvetica", 9, "bold"),
                 bg=t["bg"], fg=t["fg_label"]).pack(side="left", padx=(0, 6))

        log_choices = {
            "Apache Error Log": "/opt/lampp/logs/error_log",
            "PHP Error Log": "/opt/lampp/logs/php_error_log",
            "Apache Access Log": "/opt/lampp/logs/access_log",
            "Log de la Aplicación": LOG_PATH
        }

        combo_log = ttk.Combobox(top_bar, values=list(log_choices.keys()), state="readonly", width=22)
        combo_log.pack(side="left", padx=4)
        combo_log.set("Apache Error Log")

        tk.Label(top_bar, text="Filtro:", font=("Helvetica", 9), bg=t["bg"], fg=t["fg"]).pack(side="left", padx=(10, 4))
        ent_filter = tk.Entry(top_bar, width=15, font=("Helvetica", 9))
        ent_filter.pack(side="left")

        txt_tail = scrolledtext.ScrolledText(win, bg=t["bg_secondary"], fg=t["fg"],
                                             font=("Monospace", 9), padx=8, pady=8)
        txt_tail.pack(fill="both", expand=True, padx=12, pady=4)

        txt_tail.tag_configure("tag_err", foreground="#f38ba8", font=("Monospace", 9, "bold"))
        txt_tail.tag_configure("tag_warn", foreground="#fab387")
        txt_tail.tag_configure("tag_info", foreground="#89b4fa")
        txt_tail.tag_configure("tag_norm", foreground=t["fg"])

        state = {"active": True, "paused": False}

        def on_close():
            state["active"] = False
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", on_close)

        def tail_worker():
            import time
            selected_key = combo_log.get() if hasattr(combo_log, "get") else "Apache Error Log"
            current_target = log_choices.get(selected_key, "/opt/lampp/logs/error_log")
            f = None
            try:
                if os.path.isfile(current_target):
                    f = open(current_target, "r", encoding="utf-8", errors="replace")
                    f.seek(0, os.SEEK_END)
            except Exception:
                pass

            last_choice = selected_key

            while state.get("active", False):
                new_choice = combo_log.get() if hasattr(combo_log, "get") else "Apache Error Log"
                if new_choice != last_choice:
                    last_choice = new_choice
                    current_target = log_choices.get(new_choice, "/opt/lampp/logs/error_log")
                    if f:
                        try:
                            f.close()
                        except Exception:
                            pass
                    try:
                        if os.path.isfile(current_target):
                            f = open(current_target, "r", encoding="utf-8", errors="replace")
                            f.seek(0, os.SEEK_END)
                    except Exception:
                        pass
                    txt_tail.delete("1.0", tk.END)

                if not state["paused"] and f:
                    line = f.readline()
                    if line:
                        query = ent_filter.get().strip().lower()
                        if not query or query in line.lower():
                            lower_l = line.lower()
                            if any(k in lower_l for k in ("error", "fatal", "uncaught", "exception")):
                                tag = "tag_err"
                            elif any(k in lower_l for k in ("warning", "notice", "deprecated")):
                                tag = "tag_warn"
                            elif any(k in lower_l for k in ("notice", "info")):
                                tag = "tag_info"
                            else:
                                tag = "tag_norm"

                            def insert_line(l=line, tg=tag):
                                if win.winfo_exists():
                                    txt_tail.insert(tk.END, l, tg)
                                    txt_tail.see(tk.END)

                            self.safe_after(0, insert_line)
                    else:
                        time.sleep(0.4)
                else:
                    time.sleep(0.4)

            if f:
                try:
                    f.close()
                except Exception:
                    pass

        threading.Thread(target=tail_worker, daemon=True).start()

        btn_bar = tk.Frame(win, bg=t["bg"], padx=12, pady=8)
        btn_bar.pack(fill="x")

        def toggle_pause():
            state["paused"] = not state["paused"]
            btn_pause.configure(text="▶ Reanudar" if state["paused"] else "⏸ Pausar")

        btn_pause = tk.Button(btn_bar, text="⏸ Pausar", bg=t["bg_button"], fg=t["fg"],
                              font=("Helvetica", 9), command=toggle_pause)
        btn_pause.pack(side="left", padx=3)

        def clear_txt():
            txt_tail.delete("1.0", tk.END)

        tk.Button(btn_bar, text="🧹 Limpiar", bg=t["bg_button"], fg=t["fg"],
                  font=("Helvetica", 9), command=clear_txt).pack(side="left", padx=3)

        tk.Button(btn_bar, text="Cerrar", bg=t["bg_button"], fg=t["fg"],
                  font=("Helvetica", 9), command=on_close).pack(side="right", padx=3)

    def show_htaccess_editor(self):
        """Editor y asistente de plantillas de configuración .htaccess para el proyecto actual."""
        t = THEMES[self.current_theme]
        proj_path = self.get_selected_project()
        if not proj_path:
            return

        htaccess_path = os.path.join(proj_path, ".htaccess")
        if os.path.isdir(os.path.join(proj_path, "public")) and os.path.isfile(os.path.join(proj_path, "public", ".htaccess")):
            htaccess_path = os.path.join(proj_path, "public", ".htaccess")

        win = tk.Toplevel(self.root)
        win.title(f"Editor .htaccess - {os.path.basename(proj_path)}")
        win.geometry("620x500")
        win.transient(self.root)
        win.configure(bg=t["bg"])

        top_f = tk.Frame(win, bg=t["bg"], padx=12, pady=6)
        top_f.pack(fill="x")

        tk.Label(top_f, text=f"Archivo: {htaccess_path}", font=("Monospace", 8),
                 bg=t["bg"], fg=t["fg_label"]).pack(anchor="w")

        snip_bar = tk.Frame(win, bg=t["bg_secondary"], padx=10, pady=6)
        snip_bar.pack(fill="x", padx=12, pady=4)

        tk.Label(snip_bar, text="Plantillas:", font=("Helvetica", 8, "bold"),
                 bg=t["bg_secondary"], fg=t["fg"]).pack(side="left", padx=(0, 4))

        txt_editor = scrolledtext.ScrolledText(win, bg=t["bg_secondary"], fg=t["fg"],
                                               font=("Monospace", 9), padx=8, pady=8)
        txt_editor.pack(fill="both", expand=True, padx=12, pady=4)

        current_content = ""
        if os.path.isfile(htaccess_path):
            try:
                with open(htaccess_path, "r", encoding="utf-8", errors="replace") as f:
                    current_content = f.read()
            except Exception as e:
                write_log(f"Error leyendo {htaccess_path}: {e}")

        txt_editor.insert(tk.END, current_content)

        snippets = {
            "SPA (React/Vue)": (
                "\n# Enrutamiento SPA\n"
                "<IfModule mod_rewrite.c>\n"
                "    RewriteEngine On\n"
                "    RewriteBase /\n"
                "    RewriteRule ^index\\.html$ - [L]\n"
                "    RewriteCond %{REQUEST_FILENAME} !-f\n"
                "    RewriteCond %{REQUEST_FILENAME} !-d\n"
                "    RewriteRule . index.html [L]\n"
                "</IfModule>\n"
            ),
            "Forzar HTTPS": (
                "\n# Forzar redirección HTTPS\n"
                "<IfModule mod_rewrite.c>\n"
                "    RewriteEngine On\n"
                "    RewriteCond %{HTTPS} off\n"
                "    RewriteRule ^(.*)$ https://%{HTTP_HOST}%{REQUEST_URI} [L,R=301]\n"
                "</IfModule>\n"
            ),
            "Habilitar CORS": (
                "\n# Habilitar CORS para APIs\n"
                "<IfModule mod_headers.c>\n"
                "    Header set Access-Control-Allow-Origin \"*\"\n"
                "    Header set Access-Control-Allow-Methods \"GET, POST, OPTIONS, PUT, DELETE\"\n"
                "    Header set Access-Control-Allow-Headers \"Content-Type, Authorization\"\n"
                "</IfModule>\n"
            ),
            "Seguridad Headers": (
                "\n# Cabeceras de Seguridad\n"
                "<IfModule mod_headers.c>\n"
                "    Header set X-Content-Type-Options \"nosniff\"\n"
                "    Header set X-Frame-Options \"SAMEORIGIN\"\n"
                "    Header set X-XSS-Protection \"1; mode=block\"\n"
                "</IfModule>\n"
            ),
            "No Indexes": (
                "\n# Desactivar listado de archivos\n"
                "Options -Indexes\n"
            )
        }

        for snip_name, snip_code in snippets.items():
            tk.Button(snip_bar, text=f"+ {snip_name}", font=("Helvetica", 7, "bold"),
                      bg=t["bg_button"], fg=t["fg"],
                      command=lambda c=snip_code: (txt_editor.insert(tk.END, c), txt_editor.see(tk.END))).pack(side="left", padx=2)

        def save_htaccess():
            new_code = txt_editor.get("1.0", tk.END).strip() + "\n"
            try:
                if os.path.isfile(htaccess_path):
                    shutil.copy2(htaccess_path, htaccess_path + ".bak")
                with open(htaccess_path, "w", encoding="utf-8") as f:
                    f.write(new_code)
                self.send_notification(".htaccess guardado correctamente")
                write_log(f"Archivo .htaccess guardado en {htaccess_path}")
                messagebox.showinfo("Guardado", f"Archivo .htaccess guardado correctamente.\n(Se creó copia de seguridad .bak)")
            except Exception as ex:
                write_log(f"Error guardando .htaccess: {ex}")
                messagebox.showerror("Error", f"No se pudo guardar .htaccess:\n{ex}")

        btn_bar = tk.Frame(win, bg=t["bg"], padx=12, pady=8)
        btn_bar.pack(fill="x")

        tk.Button(btn_bar, text="💾 Guardar .htaccess", bg=t["btn_start"], fg="white",
                  font=("Helvetica", 9, "bold"), command=save_htaccess).pack(side="left", padx=4)
        tk.Button(btn_bar, text="Cerrar", bg=t["bg_button"], fg=t["fg"],
                  font=("Helvetica", 9), command=win.destroy).pack(side="right", padx=4)


LOG_MAX_BYTES = 1024 * 1024  # 1MB
LOG_MAX_FILES = 5

def write_log(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}\n"
    with LOG_LOCK:
        try:
            file_existed = os.path.exists(LOG_PATH)
            rotate_log_if_needed()
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(log_entry)
            if not file_existed:
                try:
                    os.chmod(LOG_PATH, 0o600)
                except Exception:
                    pass
        except Exception as e:
            print(f"Error escribiendo log: {e}")

def rotate_log_if_needed():
    """Rota el log si supera LOG_MAX_BYTES, conservando hasta LOG_MAX_FILES."""
    try:
        if not os.path.exists(LOG_PATH):
            return
        if os.path.getsize(LOG_PATH) < LOG_MAX_BYTES:
            return
        # Eliminar el archivo más antiguo
        oldest = f"{LOG_PATH}.{LOG_MAX_FILES}"
        if os.path.exists(oldest):
            os.remove(oldest)
        # Desplazar los archivos .N -> .N+1
        for i in range(LOG_MAX_FILES - 1, 0, -1):
            src = f"{LOG_PATH}.{i}"
            dst = f"{LOG_PATH}.{i + 1}"
            if os.path.exists(src):
                os.replace(src, dst)
        # Renombrar el log actual a .1
        os.replace(LOG_PATH, f"{LOG_PATH}.1")
    except Exception as e:
        print(f"Error rotando log: {e}")

if __name__ == "__main__":
    XamppGUI()
