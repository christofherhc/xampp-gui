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
from urllib.parse import quote

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
        if service_name and service_name in cmdline:
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
        
        self.btn_refresh_projects = tk.Button(self.frame_projects, text="🔄", width=3,
                                              font=("Helvetica", 9, "bold"),
                                              command=self.load_projects)
        self.btn_refresh_projects.grid(row=0, column=3, padx=2, pady=2)

        self.btn_new_project = tk.Button(self.frame_projects, text="➕", width=3,
                                         font=("Helvetica", 9, "bold"),
                                         command=self.new_project)
        self.btn_new_project.grid(row=0, column=4, padx=2, pady=2)
        
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
                           "XAMPP Control Center v2.2\n\n"
                           "Interfaz gráfica para administrar XAMPP en Linux (Mint, Ubuntu, Debian).\n\n"
                           f"Servicios detectados: {installed}\n"
                           "Características: Detección anti-colisión, auto-refresh,\n"
                           "gestor de proyectos, logs integrados, temas claro/oscuro.")

    def _port_open(self, host, port, timeout=1.0):
        """Comprueba si un puerto responde en localhost."""
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except Exception:
            return False

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
        name = os.path.basename(path)
        url = f"http://localhost/{quote(name)}"
        write_log(f"Abriendo proyecto en navegador: {url}")
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
