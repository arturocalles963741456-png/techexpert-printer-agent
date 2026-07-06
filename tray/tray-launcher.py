#!/usr/bin/env python3
"""
TechExpert TPV — Printer Agent Tray Launcher v2.0
Professional desktop tray app with first-run config wizard.
Icono T.E. en barra de menú, ventana de configuración, auto-arranque.
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, GdkPixbuf, Pango
import subprocess
import os
import sys
import json
import signal
import shutil
import threading
import webbrowser
from datetime import datetime

APP_NAME = "TechExpert Printer Agent"
APP_VERSION = "2.0.0"
AGENT_SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'agent.js')
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, 'config.json')

# ── Config paths ──
CONFIG_DIR = os.path.join(os.path.expanduser('~'), '.techexpert')
AGENT_LOG = os.path.join(CONFIG_DIR, 'agent.log')
PID_FILE = os.path.join(CONFIG_DIR, 'agent.pid')
SETTINGS_FILE = os.path.join(CONFIG_DIR, 'tray-settings.json')

# ── Icon ──
ICON_SVG = os.path.join(os.path.dirname(__file__), 'icon.svg')
ICON_PNG = os.path.join(os.path.dirname(__file__), 'icon.png')

# ── Agent config defaults ──
DEFAULT_CONFIG = {
    "tunnel_url": "wss://sattpv.techexpert.cloud/tunnel/agent",
    "printer_host": "127.0.0.1",
    "printer_port": 9100,
    "agent_port": 19100,
    "printer_type": "auto",
    "token": ""
}

# Global state
agent_process = None
status_icon = None
menu = None
status_label = None
status_icon_name = None
auto_start = False
observers = []

# ═══════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════

def load_config():
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH) as f:
                cfg = json.load(f)
                # Merge with defaults
                for k, v in DEFAULT_CONFIG.items():
                    if k not in cfg:
                        cfg[k] = v
                return cfg
    except:
        pass
    return dict(DEFAULT_CONFIG)

def save_config(cfg):
    try:
        with open(CONFIG_PATH, 'w') as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        log(f"Error guardando config: {e}")

def has_valid_token():
    cfg = load_config()
    return bool(cfg.get('token', '').strip())

def ensure_dirs():
    os.makedirs(CONFIG_DIR, exist_ok=True)

def load_settings():
    global auto_start
    try:
        with open(SETTINGS_FILE) as f:
            s = json.load(f)
            auto_start = s.get('auto_start', False)
    except:
        auto_start = False

def save_settings():
    with open(SETTINGS_FILE, 'w') as f:
        json.dump({'auto_start': auto_start}, f)

# ═══════════════════════════════════════════
#  LOGGING
# ═══════════════════════════════════════════

log_buffer = None

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    line = f'[{ts}] {msg}'
    print(line)
    if log_buffer:
        GLib.idle_add(lambda: log_buffer.insert(log_buffer.get_end_iter(), line + '\n'))
    try:
        with open(AGENT_LOG, 'a') as f:
            f.write(line + '\n')
    except:
        pass

# ═══════════════════════════════════════════
#  AGENT MANAGEMENT
# ═══════════════════════════════════════════

def get_node_path():
    base = BASE_DIR
    for cand in [
        os.path.join(base, 'agent.exe'),
        os.path.join(base, 'agent'),
        os.path.join(base, 'agent.js'),
    ]:
        if os.path.exists(cand):
            return cand
    return None

def update_status(text, icon='offline'):
    if status_label:
        GLib.idle_add(lambda: status_label.set_markup(
            f'<span size="small">{text}</span>'
        ))
    if status_icon_name and status_icon:
        icons = {'online': '🟢', 'offline': '🔴', 'starting': '🟡', 'error': '🔴'}
        prefix = icons.get(icon, '')
        GLib.idle_add(lambda: status_icon.set_tooltip_text(
            f"{APP_NAME} v{APP_VERSION} — {prefix} {text}"
        ))

def start_agent(btn=None):
    global agent_process
    if agent_process and agent_process.poll() is None:
        log("Agent ya está en ejecución")
        return

    if not has_valid_token():
        log("❌ No hay token configurado")
        show_config_dialog()
        return

    node = get_node_path()
    if not node:
        log("❌ No se encuentra el binario del agent")
        update_status("Error: binario no encontrado", 'error')
        return

    log("🚀 Iniciando Printer Agent...")
    update_status("Iniciando...", 'starting')

    try:
        agent_process = subprocess.Popen(
            [node],
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True
        )
        with open(PID_FILE, 'w') as f:
            f.write(str(agent_process.pid))
        log(f"✅ PID: {agent_process.pid}")

        def reader():
            for line in iter(agent_process.stdout.readline, ''):
                if line:
                    l = line.strip()
                    log(l)
                    if '✅ Authenticated' in l or 'auth_ok' in l:
                        update_status("Conectado ✅", 'online')
                    elif '❌' in l:
                        update_status("Error de conexión", 'error')
                    elif 'Connected to tunnel' in l:
                        update_status("Conectando...", 'starting')
            agent_process.stdout.close()

        threading.Thread(target=reader, daemon=True).start()

        def waiter():
            agent_process.wait()
            GLib.idle_add(lambda: on_agent_stopped())
        threading.Thread(target=waiter, daemon=True).start()

    except Exception as e:
        log(f"❌ Error: {e}")
        update_status("Error al iniciar", 'error')

def stop_agent():
    global agent_process
    if agent_process and agent_process.poll() is None:
        log("🛑 Deteniendo agent...")
        agent_process.terminate()
        try:
            agent_process.wait(timeout=5)
        except:
            agent_process.kill()
        agent_process = None
        try:
            os.remove(PID_FILE)
        except:
            pass
        log("✅ Detenido")
        update_status("Detenido", 'offline')
    else:
        log("Agent no está en ejecución")

def on_agent_stopped():
    global agent_process
    log("⚠️ Proceso terminado")
    agent_process = None
    update_status("Desconectado", 'offline')

# ═══════════════════════════════════════════
#  CONFIG DIALOG (Professional setup wizard)
# ═══════════════════════════════════════════

def show_config_dialog():
    cfg = load_config()
    dialog = Gtk.Dialog(
        title=f"TechExpert Printer Agent — Configuración",
        transient_for=None,
        flags=Gtk.DialogFlags.MODAL,
        buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK)
    )
    dialog.set_default_size(520, 480)
    dialog.set_resizable(False)
    dialog.set_position(Gtk.WindowPosition.CENTER)

    # Try to set icon
    if os.path.exists(ICON_PNG):
        try:
            dialog.set_icon_from_file(ICON_PNG)
        except:
            pass

    # ── Header with branding ──
    header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    header.set_margin_start(20)
    header.set_margin_end(20)
    header.set_margin_top(20)

    title_label = Gtk.Label()
    title_label.set_markup('<span size="x-large" weight="bold">TechExpert Printer Agent</span>')
    header.pack_start(title_label, False, False, 0)

    subtitle = Gtk.Label(label="Configuración de impresora térmica")
    subtitle.get_style_context().add_class('text-muted')
    header.pack_start(subtitle, False, False, 0)

    # Separator
    sep = Gtk.HSeparator()
    sep.set_margin_top(12)
    sep.set_margin_bottom(12)
    header.pack_start(sep, False, False, 0)

    dialog.get_content_area().pack_start(header, False, False, 0)

    # ── Main form ──
    form = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    form.set_margin_start(20)
    form.set_margin_end(20)
    form.set_margin_bottom(20)

    # Token
    token_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    token_label = Gtk.Label(label="Token de conexión *", xalign=0)
    token_label.set_markup('<b>Token de conexión</b> *')
    token_box.pack_start(token_label, False, False, 0)

    token_entry = Gtk.Entry()
    token_entry.set_placeholder_text("Pega aquí el token del panel Administración → Impresora")
    token_entry.set_text(cfg.get('token', ''))
    token_entry.set_width_chars(40)
    token_box.pack_start(token_entry, False, False, 0)

    # Token help
    token_help = Gtk.Label(xalign=0)
    token_help.set_markup('<a href="">¿Dónde encuentro el token?</a>')
    token_help.set_halign(Gtk.Align.START)
    token_help.connect('activate-link', lambda *a: webbrowser.open('https://sattpv.techexpert.cloud/#/admin'))
    token_box.pack_start(token_help, False, False, 0)

    form.pack_start(token_box, False, False, 0)

    # Separator
    sep2 = Gtk.HSeparator()
    sep2.set_margin_top(8)
    sep2.set_margin_bottom(8)
    form.pack_start(sep2, False, False, 0)

    # Printer type
    type_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    type_label = Gtk.Label(label="Tipo de impresora", xalign=0)
    type_label.set_markup('<b>Tipo de impresora</b>')
    type_box.pack_start(type_label, False, False, 0)

    type_combo = Gtk.ComboBoxText()
    type_combo.append('auto', 'Automático (USB → Red)')
    type_combo.append('network', 'Red TCP/IP')
    type_combo.append('usb', 'USB directo')
    type_combo.set_active_id(cfg.get('printer_type', 'auto'))
    type_box.pack_start(type_combo, False, False, 0)

    type_note = Gtk.Label(xalign=0)
    type_note.set_markup('<span size="small" color="grey">"Automático" prueba USB primero, si no encuentra cae a red.</span>')
    type_box.pack_start(type_note, False, False, 0)

    form.pack_start(type_box, False, False, 0)

    # Network settings frame
    net_frame = Gtk.Frame(label="Configuración de red")
    net_frame.set_margin_top(8)
    net_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    net_vbox.set_margin_start(8)
    net_vbox.set_margin_end(8)
    net_vbox.set_margin_top(8)
    net_vbox.set_margin_bottom(8)

    ip_hbox = Gtk.Box(spacing=8)
    ip_label = Gtk.Label(label="Dirección IP:", xalign=0)
    ip_label.set_width_chars(14)
    ip_entry = Gtk.Entry()
    ip_entry.set_text(cfg.get('printer_host', '127.0.0.1'))
    ip_entry.set_width_chars(20)
    ip_hbox.pack_start(ip_label, False, False, 0)
    ip_hbox.pack_start(ip_entry, True, True, 0)
    net_vbox.pack_start(ip_hbox, False, False, 0)

    port_hbox = Gtk.Box(spacing=8)
    port_label = Gtk.Label(label="Puerto:", xalign=0)
    port_label.set_width_chars(14)
    port_spin = Gtk.SpinButton()
    port_spin.set_range(1, 65535)
    port_spin.set_value(cfg.get('printer_port', 9100))
    port_spin.set_width_chars(6)
    port_hbox.pack_start(port_label, False, False, 0)
    port_hbox.pack_start(port_spin, False, False, 0)
    net_vbox.pack_start(port_hbox, False, False, 0)

    net_frame.add(net_vbox)
    form.pack_start(net_frame, False, False, 0)

    # Auto-start checkbox
    auto_check = Gtk.CheckButton(label="Iniciar automáticamente al iniciar sesión")
    auto_check.set_active(auto_start)
    auto_check.set_margin_top(12)
    form.pack_start(auto_check, False, False, 0)

    dialog.get_content_area().pack_start(form, True, True, 0)

    dialog.show_all()

    response = dialog.run()
    if response == Gtk.ResponseType.OK:
        new_cfg = {
            'tunnel_url': DEFAULT_CONFIG['tunnel_url'],
            'printer_host': ip_entry.get_text().strip(),
            'printer_port': int(port_spin.get_value()),
            'agent_port': DEFAULT_CONFIG['agent_port'],
            'printer_type': type_combo.get_active_id() or 'auto',
            'token': token_entry.get_text().strip()
        }
        save_config(new_cfg)
        global auto_start
        auto_start = auto_check.get_active()
        save_settings()
        if auto_start:
            setup_autostart(True)

        log("✅ Configuración guardada")
        if new_cfg['token']:
            update_status("Configurado, listo para iniciar", 'offline')
            # Auto-start agent if token was missing
            if not cfg.get('token', '').strip():
                start_agent()
    else:
        log("Configuración cancelada")

    dialog.destroy()

# ═══════════════════════════════════════════
#  AUTOSTART
# ═══════════════════════════════════════════

def toggle_startup():
    global auto_start
    auto_start = not auto_start
    save_settings()
    setup_autostart(auto_start)
    log(f"Auto-arranque: {'ON' if auto_start else 'OFF'}")

def setup_autostart(enabled):
    """Configure autostart per platform"""
    platform = sys.platform
    launcher = os.path.abspath(__file__)
    icon_path = ICON_PNG if os.path.exists(ICON_PNG) else ICON_SVG

    if platform == 'linux':
        desktop_path = os.path.join(os.path.expanduser('~'), '.config', 'autostart')
        os.makedirs(desktop_path, exist_ok=True)
        desktop_file = os.path.join(desktop_path, 'techexpert-printer-agent.desktop')

        if enabled:
            with open(desktop_file, 'w') as f:
                f.write(f"""[Desktop Entry]
Type=Application
Name=TechExpert Printer Agent
Comment=Printer agent for TechExpert TPV
Exec=python3 {launcher} --tray
Icon={icon_path}
Terminal=false
Categories=Network;Utility;
X-GNOME-Autostart-enabled=true
""")
            log(f"✅ Autostart Linux: {desktop_file}")
        else:
            if os.path.exists(desktop_file):
                os.remove(desktop_file)
                log("Autostart eliminado")

    elif platform == 'darwin':
        plist_path = os.path.join(os.path.expanduser('~'), 'Library', 'LaunchAgents')
        os.makedirs(plist_path, exist_ok=True)
        plist_file = os.path.join(plist_path, 'com.techexpert.printer-agent.plist')

        if enabled:
            with open(plist_file, 'w') as f:
                f.write(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.techexpert.printer-agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>{launcher}</string>
        <string>--tray</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>{AGENT_LOG}</string>
    <key>StandardErrorPath</key>
    <string>{AGENT_LOG}</string>
</dict>
</plist>
""")
            log(f"✅ LaunchAgent macOS: {plist_file}")
        else:
            if os.path.exists(plist_file):
                os.remove(plist_file)
                log("LaunchAgent eliminado")

    elif platform == 'win32':
        try:
            import winreg
            key_path = r'Software\Microsoft\Windows\CurrentVersion\Run'
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            if enabled:
                winreg.SetValueEx(key, 'TechExpertPrinterAgent', 0, winreg.REG_SZ,
                                  f'pythonw.exe "{launcher}" --tray')
                log("✅ Autostart Windows")
            else:
                try:
                    winreg.DeleteValue(key, 'TechExpertPrinterAgent')
                    log("Autostart eliminado")
                except:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            log(f"Error autostart Windows: {e}")

# ═══════════════════════════════════════════
#  LOG WINDOW
# ═══════════════════════════════════════════

def show_log_window():
    global log_buffer
    win = Gtk.Window(title=f"{APP_NAME} — Registro")
    win.set_default_size(650, 420)
    win.set_position(Gtk.WindowPosition.CENTER)
    if os.path.exists(ICON_PNG):
        try:
            win.set_icon_from_file(ICON_PNG)
        except:
            pass

    scrolled = Gtk.ScrolledWindow()
    scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

    log_buffer = Gtk.TextBuffer()
    text_view = Gtk.TextView(buffer=log_buffer)
    text_view.set_editable(False)
    text_view.set_cursor_visible(True)
    text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
    text_view.override_font(Pango.FontDescription('SF Mono, Menlo, monospace 10'))

    # Colors for readability
    tag_ok = log_buffer.create_tag("ok", foreground="#16a34a")
    tag_err = log_buffer.create_tag("err", foreground="#dc2626")
    tag_info = log_buffer.create_tag("info", foreground="#2563eb")

    scrolled.add(text_view)

    # Load existing log
    if os.path.exists(AGENT_LOG):
        try:
            with open(AGENT_LOG) as f:
                log_buffer.set_text(f.read())
        except:
            pass

    vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

    # Toolbar
    toolbar = Gtk.Box(spacing=6)
    toolbar.set_margin_start(6)
    toolbar.set_margin_end(6)
    toolbar.set_margin_top(6)

    refresh_btn = Gtk.Button(label="🔄 Recargar")
    def on_refresh(*a):
        log_buffer.set_text('')
        if os.path.exists(AGENT_LOG):
            try:
                with open(AGENT_LOG) as f:
                    log_buffer.set_text(f.read())
            except:
                pass
    refresh_btn.connect('clicked', on_refresh)
    toolbar.pack_start(refresh_btn, False, False, 0)

    clear_btn = Gtk.Button(label="🗑 Limpiar")
    def on_clear(*a):
        log_buffer.set_text('')
        try: open(AGENT_LOG, 'w').close()
        except: pass
    clear_btn.connect('clicked', on_clear)
    toolbar.pack_start(clear_btn, False, False, 0)

    toolbar.pack_end(Gtk.Label(label=f"v{APP_VERSION}"), False, False, 0)

    vbox.pack_start(toolbar, False, False, 0)
    vbox.pack_start(scrolled, True, True, 0)

    # Close button
    close_btn = Gtk.Button(label="Cerrar")
    close_btn.connect('clicked', lambda *a: win.destroy())
    close_box = Gtk.Box()
    close_box.pack_end(close_btn, False, False, 6)
    close_box.set_margin_bottom(6)
    close_box.set_margin_end(6)
    vbox.pack_end(close_box, False, False, 0)

    win.add(vbox)
    win.show_all()

# ═══════════════════════════════════════════
#  ABOUT
# ═══════════════════════════════════════════

def show_about():
    about = Gtk.AboutDialog()
    about.set_program_name(APP_NAME)
    about.set_version(APP_VERSION)
    about.set_comments("Agente de impresión térmica para TechExpert TPV\nConecta tu impresora al sistema vía túnel WebSocket.")
    about.set_copyright("© 2026 TechExpert")
    about.set_website("https://techexpert.cloud")
    about.set_website_label("techexpert.cloud")
    about.set_authors(["TechExpert Team"])
    if os.path.exists(ICON_PNG):
        try:
            about.set_logo(GdkPixbuf.Pixbuf.new_from_file(ICON_PNG))
        except:
            pass
    about.set_license("""
MIT License

Copyright (c) 2026 TechExpert

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction...
""")
    about.run()
    about.destroy()

# ═══════════════════════════════════════════
#  TRAY MENU
# ═══════════════════════════════════════════

def build_menu():
    global menu, status_label

    menu = Gtk.Menu()

    # Header
    header_item = Gtk.MenuItem()
    hbox = Gtk.Box(spacing=8)
    hbox.set_margin_start(4)
    hbox.set_margin_end(4)

    icon_img = Gtk.Image()
    if os.path.exists(ICON_PNG):
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(ICON_PNG, 24, 24)
            icon_img.set_from_pixbuf(pixbuf)
        except:
            icon_img.set_from_stock(Gtk.STOCK_PRINT, Gtk.IconSize.MENU)
    hbox.pack_start(icon_img, False, False, 0)

    vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
    name_lbl = Gtk.Label(label="TechExpert TPV", xalign=0)
    name_lbl.set_markup('<b>TechExpert TPV</b>')
    vbox.pack_start(name_lbl, False, False, 0)

    status_label = Gtk.Label(label="Estado: Inactivo", xalign=0)
    status_label.set_markup('<span size="small">Estado: Inactivo</span>')
    vbox.pack_start(status_label, False, False, 0)

    hbox.pack_start(vbox, True, True, 0)
    header_item.add(hbox)
    header_item.set_sensitive(False)
    menu.append(header_item)

    menu.append(Gtk.SeparatorMenuItem())

    # Start
    start_item = Gtk.MenuItem(label="▶ Iniciar agente")
    start_item.connect('activate', lambda *a: start_agent())
    menu.append(start_item)

    # Stop
    stop_item = Gtk.MenuItem(label="⏹ Detener agente")
    stop_item.connect('activate', lambda *a: stop_agent())
    menu.append(stop_item)

    # Restart
    restart_item = Gtk.MenuItem(label="🔄 Reiniciar")
    restart_item.connect('activate', lambda *a: [stop_agent(), start_agent()])
    menu.append(restart_item)

    menu.append(Gtk.SeparatorMenuItem())

    # Configure
    config_item = Gtk.MenuItem(label="⚙ Configuración...")
    config_item.connect('activate', lambda *a: show_config_dialog())
    menu.append(config_item)

    # Auto-start
    global auto_start
    auto_item = Gtk.CheckMenuItem(label="Iniciar con el sistema")
    auto_item.set_active(auto_start)
    auto_item.connect('toggled', lambda *a: toggle_startup())
    menu.append(auto_item)

    menu.append(Gtk.SeparatorMenuItem())

    # Log
    log_item = Gtk.MenuItem(label="📋 Ver logs")
    log_item.connect('activate', lambda *a: show_log_window())
    menu.append(log_item)

    menu.append(Gtk.SeparatorMenuItem())

    # About
    about_item = Gtk.MenuItem(label="ℹ Acerca de")
    about_item.connect('activate', lambda *a: show_about())
    menu.append(about_item)

    menu.append(Gtk.SeparatorMenuItem())

    # Quit
    quit_item = Gtk.MenuItem(label="❌ Salir")
    quit_item.connect('activate', lambda *a: quit_app())
    menu.append(quit_item)

    menu.show_all()

# ═══════════════════════════════════════════
#  ICON GENERATION
# ═══════════════════════════════════════════

def create_icon():
    """Generate PNG from SVG if not exists"""
    if os.path.exists(ICON_PNG):
        return ICON_PNG

    try:
        import cairosvg
        cairosvg.svg2png(url=ICON_SVG, write_to=ICON_PNG, output_width=256, output_height=256)
        return ICON_PNG
    except:
        pass

    try:
        subprocess.run(['rsvg-convert', ICON_SVG, '-o', ICON_PNG, '-w', '256', '-h', '256'],
                       capture_output=True)
        if os.path.exists(ICON_PNG):
            return ICON_PNG
    except:
        pass

   # Fallback: create minimal PNG
    try:
        create_minimal_png(ICON_PNG, 256)
        return ICON_PNG
    except:
        pass

    return ICON_SVG

def create_minimal_png(path, size=256):
    """Create PNG programmatically using struct + zlib"""
    import struct
    import zlib

    def write_chunk(f, chunk_type, data):
        f.write(struct.pack('>I', len(data)))
        f.write(chunk_type)
        f.write(data)
        crc = zlib.crc32(chunk_type + data) & 0xffffffff
        f.write(struct.pack('>I', crc))

    raw_data = b''
    for y in range(size):
        raw_data += b'\x00'
        for x in range(size):
            r = int(37 + (x / size) * 10)
            g = int(99 + (y / size) * 10)
            b_val = int(235 - (y / size) * 20)
            a = 255

            # Rounded corners (radius ~18%)
            rx, ry = size * 0.18, size * 0.18
            dx = x if x < size - x else size - x
            dy = y if y < size - y else size - y
            if dx < rx and dy < ry:
                dist = ((rx - dx) ** 2 + (ry - dy) ** 2) ** 0.5
                if dist > rx:
                    r, g, b_val, a = 0, 0, 0, 0

            # "TE" - thick white letters
            cx, cy = size // 2, size // 2
            # T vertical:  x 108-148, y 100-380
            if 108 <= x <= 148 and 100 <= y <= 380:
                r, g, b_val = 255, 255, 255
            # T horizontal:  y 70-110, x 70-380
            if 70 <= y <= 110 and 70 <= x <= 380:
                r, g, b_val = 255, 255, 255
            # E top:  y 230-270, x 200-380
            if 230 <= y <= 270 and 200 <= x <= 380:
                r, g, b_val = 255, 255, 255
            # E middle:  y 300-340, x 200-370
            if 300 <= y <= 340 and 200 <= x <= 370:
                r, g, b_val = 255, 255, 255
            # E bottom:  y 370-410, x 200-380
            if 370 <= y <= 410 and 200 <= x <= 380:
                r, g, b_val = 255, 255, 255

            raw_data += struct.pack('BBBB', r, g, b_val, a)

    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        write_chunk(f, b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0))
        compressed = zlib.compress(raw_data)
        write_chunk(f, b'IDAT', compressed)
        write_chunk(f, b'IEND', b'')

# ═══════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════

def quit_app(*args):
    log("👋 Cerrando TechExpert Tray...")
    stop_agent()
    Gtk.main_quit()

def run_tray():
    global status_icon

    icon_path = create_icon()
    ensure_dirs()
    load_settings()

    pixbuf = GdkPixbuf.Pixbuf.new_from_file(icon_path) if icon_path.endswith('.png') else \
             GdkPixbuf.Pixbuf.new_from_file_at_size(icon_path, 64, 64)

    status_icon = Gtk.StatusIcon()
    status_icon.set_from_pixbuf(pixbuf)
    status_icon.set_tooltip_text(f"{APP_NAME} v{APP_VERSION}")
    status_icon.connect('popup-menu', lambda icon, btn, time: menu.popup(None, None, None, None, btn, time))
    status_icon.connect('activate', lambda *a: menu.popup(None, None, None, None, 0, Gtk.get_current_event_time()))

    build_menu()
    update_status("Detenido", 'offline')

    log(f"🖥 TechExpert Tray v{APP_VERSION}")
    log(f"   Directorio: {BASE_DIR}")
    log(f"   Config: {CONFIG_PATH}")

    # First run: show config dialog if no token
    if not has_valid_token():
        log("🔑 Primera ejecución — solicitando token")
        GLib.idle_add(show_config_dialog)
    else:
        log(f"🔑 Token configurado ({load_config()['token'][:16]}...)")

    # Auto-start if configured
    if auto_start:
        log("⚡ Auto-arranque activo")
        GLib.idle_add(start_agent)

    Gtk.main()

def run_headless():
    """Run without tray (for autostart / headless)"""
    ensure_dirs()
    load_settings()

    if not has_valid_token():
        log("❌ No hay token. Ejecuta con --tray para configurar.")
        return

    log("Modo headless — iniciando agente")
    start_agent()
    signal.pause()

def main():
    if '--gen-icon' in sys.argv:
        create_icon()
        print(f"Icon: {ICON_PNG}")
        return
    if '--tray' in sys.argv:
        run_tray()
    elif '--headless' in sys.argv:
        run_headless()
    elif '--version' in sys.argv:
        print(f"{APP_NAME} v{APP_VERSION}")
    else:
        try:
            run_tray()
        except Exception as e:
            print(f"Tray no disponible ({e}), modo headless")
            run_headless()

if __name__ == '__main__':
    main()
