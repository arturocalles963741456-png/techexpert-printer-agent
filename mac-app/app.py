#!/usr/bin/env python3
"""
TechExpert Printer Agent — macOS Native App
White background, blue text, professional T.E. branding.
Controls agent.js via stdin/stdout JSON protocol.
"""

import tkinter as tk
from tkinter import ttk
import subprocess
import os
import sys
import json
import threading
import time

APP_VERSION = "2.0.0"
APP_NAME = "TechExpert Printer Agent"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENT_BIN = os.path.join(BASE_DIR, 'agent')
if not os.path.exists(AGENT_BIN):
    AGENT_BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agent.js')
    if not os.path.exists(AGENT_BIN):
        AGENT_BIN = os.path.join(BASE_DIR, 'agent.js')
CONFIG_PATH = os.path.join(BASE_DIR, 'config.json')
ICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.png')

# Colors
WHITE = "#FFFFFF"
BG_LIGHT = "#F8FAFC"
PRIMARY_BLUE = "#2563EB"
BLUE_LIGHT = "#DBEAFE"
BLUE_DARK = "#1E40AF"
TEXT_DARK = "#1E293B"
TEXT_MUTED = "#64748B"
GREEN = "#16A34A"
RED = "#DC2626"
GRAY = "#E2E8F0"
BORDER = "#CBD5E1"

# Globals
agent_process = None
agent_stdin = None
agent_connected = False
monitor_active = False
stdin_cmd_lock = threading.Lock()

def load_config():
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except:
        return {"token": "", "printer_host": "127.0.0.1", "printer_port": 9100}

def save_config(cfg):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(cfg, f, indent=2)


class TechExpertApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.configure(bg=WHITE)

        win_w, win_h = 420, 580
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - win_w) // 2
        y = (sh - win_h) // 2
        self.root.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.root.resizable(False, False)
        self.root.attributes('-topmost', True)

        if os.path.exists(ICON_PATH):
            try:
                icon = tk.PhotoImage(file=ICON_PATH)
                self.root.iconphoto(True, icon)
            except:
                pass

        self.token = load_config().get('token', '')
        self._build_ui()

        if self.token:
            self.root.after(500, self.do_connect)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self):
        main = tk.Frame(self.root, bg=WHITE, padx=24, pady=20)
        main.pack(fill=tk.BOTH, expand=True)

        # Header
        header = tk.Frame(main, bg=WHITE)
        header.pack(fill=tk.X, pady=(0, 4))

        title = tk.Label(header, text="TechExpert", font=("Helvetica Neue", 22, "bold"),
                         fg=PRIMARY_BLUE, bg=WHITE)
        title.pack()
        subtitle = tk.Label(header, text="Printer Agent", font=("Helvetica Neue", 12),
                            fg=TEXT_MUTED, bg=WHITE)
        subtitle.pack()

        # Status
        self.status_frame = tk.Frame(main, bg=WHITE)
        self.status_frame.pack(fill=tk.X, pady=(8, 0))
        self.status_dot = tk.Canvas(self.status_frame, width=12, height=12,
                                     bg=WHITE, highlightthickness=0)
        self.status_dot.pack(side=tk.LEFT, padx=(0, 6))
        self._dot = self.status_dot.create_oval(0, 0, 12, 12, fill=GRAY, outline="")
        self.status_text = tk.Label(self.status_frame, text="Desconectado",
                                    font=("Helvetica Neue", 11), fg=TEXT_MUTED, bg=WHITE)
        self.status_text.pack(side=tk.LEFT)

        sep = tk.Frame(main, bg=GRAY, height=1)
        sep.pack(fill=tk.X, pady=12)

        # Token section
        self.token_section = tk.Frame(main, bg=WHITE)
        self.token_section.pack(fill=tk.X)

        tk.Label(self.token_section, text="Token de conexión",
                 font=("Helvetica Neue", 11, "bold"), fg=TEXT_DARK, bg=WHITE).pack(anchor=tk.W)
        tk.Label(self.token_section, text="Copia el token desde el panel Administración → Impresora",
                 font=("Helvetica Neue", 9), fg=TEXT_MUTED, bg=WHITE).pack(anchor=tk.W, pady=(0, 6))

        self.token_entry = tk.Entry(self.token_section, font=("Menlo", 10),
                                    fg=TEXT_DARK, bg=BG_LIGHT, relief="solid", borderwidth=1,
                                    highlightthickness=1, highlightcolor=PRIMARY_BLUE,
                                    highlightbackground=BORDER)
        self.token_entry.insert(0, self.token)
        self.token_entry.pack(fill=tk.X, ipady=6)

        self.connect_btn = tk.Button(self.token_section, text="Conectar",
                                     font=("Helvetica Neue", 12, "bold"),
                                     bg=PRIMARY_BLUE, fg=WHITE,
                                     activebackground=BLUE_DARK, activeforeground=WHITE,
                                     relief="flat", borderwidth=0,
                                     padx=20, pady=8, cursor="hand2",
                                     command=self.do_connect)
        self.connect_btn.pack(fill=tk.X, pady=(10, 0), ipady=2)

        # Connected section
        self.connected_section = tk.Frame(main, bg=WHITE)

        account_card = tk.Frame(self.connected_section, bg=BLUE_LIGHT,
                                highlightbackground=PRIMARY_BLUE, highlightthickness=1,
                                padx=16, pady=12)
        account_card.pack(fill=tk.X, pady=(8, 0))

        tk.Label(account_card, text="CUENTA CONECTADA",
                 font=("Helvetica Neue", 8, "bold"), fg=PRIMARY_BLUE, bg=BLUE_LIGHT).pack(anchor=tk.W)

        self.acc_name = tk.Label(account_card, text="TechExpert",
                                 font=("Helvetica Neue", 13, "bold"), fg=TEXT_DARK, bg=BLUE_LIGHT)
        self.acc_name.pack(anchor=tk.W, pady=(2, 0))

        self.acc_user = tk.Label(account_card, text="Agente conectado vía túnel",
                                 font=("Helvetica Neue", 10), fg=TEXT_MUTED, bg=BLUE_LIGHT)
        self.acc_user.pack(anchor=tk.W)

        self.printer_label = tk.Label(account_card, text="",
                                      font=("Helvetica Neue", 9), fg=TEXT_MUTED, bg=BLUE_LIGHT)
        self.printer_label.pack(anchor=tk.W)

        # Actions
        actions_frame = tk.Frame(self.connected_section, bg=WHITE)
        actions_frame.pack(fill=tk.X, pady=(14, 0))

        tk.Label(actions_frame, text="ACCIONES",
                 font=("Helvetica Neue", 9, "bold"), fg=TEXT_MUTED, bg=WHITE).pack(anchor=tk.W, pady=(0, 6))

        # Row 1: Test Ticket + Drawer
        btn_row = tk.Frame(actions_frame, bg=WHITE)
        btn_row.pack(fill=tk.X)

        self.test_btn = self._mkbtn(btn_row, "🧾 Probar ticket", PRIMARY_BLUE, self.do_test_print)
        self.test_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        self.drawer_btn = self._mkbtn(btn_row, "💰 Abrir cajón", PRIMARY_BLUE, self.do_open_drawer)
        self.drawer_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        # Row 2: Disconnect + Printer status
        btn_row2 = tk.Frame(actions_frame, bg=WHITE)
        btn_row2.pack(fill=tk.X, pady=(8, 0))

        self.status_btn = self._mkbtn(btn_row2, "🔍 Estado", PRIMARY_BLUE, self.do_get_status)
        self.status_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        self.disconnect_btn = self._mkbtn(btn_row2, "❌ Desconectar", RED, self.do_disconnect)
        self.disconnect_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        # Log
        self.log_frame = tk.Frame(main, bg=WHITE)
        self.log_frame.pack(fill=tk.BOTH, expand=True, pady=(12, 0))

        self.result_text = tk.Text(self.log_frame, font=("Menlo", 9),
                                   fg=TEXT_DARK, bg=BG_LIGHT,
                                   relief="solid", borderwidth=1,
                                   height=6, width=40, state=tk.DISABLED)
        self.result_text.pack(fill=tk.BOTH, expand=True)
        scroll = tk.Scrollbar(self.result_text)
        self.result_text.configure(yscrollcommand=scroll.set)
        scroll.config(command=self.result_text.yview)

        # Footer
        footer = tk.Frame(main, bg=WHITE)
        footer.pack(fill=tk.X, side=tk.BOTTOM, pady=(4, 0))
        tk.Label(footer, text=f"v{APP_VERSION} | sattpv.techexpert.cloud",
                 font=("Helvetica Neue", 8), fg=TEXT_MUTED, bg=WHITE).pack(side=tk.RIGHT)

    def _mkbtn(self, parent, text, color, cmd):
        return tk.Button(parent, text=text, font=("Helvetica Neue", 10, "bold"),
                         bg=color, fg=WHITE, activebackground=BLUE_DARK,
                         activeforeground=WHITE, relief="flat", borderwidth=0,
                         padx=12, pady=8, cursor="hand2", command=cmd)

    def _set_status(self, text, color, dot_color):
        self.status_text.config(text=text, fg=color)
        self.status_dot.itemconfig(self._dot, fill=dot_color)

    def _log(self, msg, color=TEXT_DARK):
        self.result_text.config(state=tk.NORMAL)
        tag = "c" + str(hash(color))
        self.result_text.tag_configure(tag, foreground=color)
        self.result_text.insert(tk.END, f"▸ {msg}\n", tag)
        self.result_text.see(tk.END)
        self.result_text.config(state=tk.DISABLED)

    # ── Agent process management ──

    def _start_agent_process(self, token):
        global agent_process, agent_stdin, monitor_active
        self._stop_agent_process()

        cfg = load_config()
        cfg['token'] = token
        save_config(cfg)

        if not os.path.exists(AGENT_BIN):
            self._log(f"❌ Binario no encontrado: {AGENT_BIN}", RED)
            return False

        try:
            agent_process = subprocess.Popen(
                [AGENT_BIN],
                cwd=os.path.dirname(AGENT_BIN) or BASE_DIR,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                universal_newlines=True
            )
            agent_stdin = agent_process.stdin
            monitor_active = True
            threading.Thread(target=self._monitor_stdout, daemon=True).start()
            return True
        except Exception as e:
            self._log(f"❌ Error iniciando agente: {e}", RED)
            return False

    def _stop_agent_process(self):
        global agent_process, agent_stdin, monitor_active
        monitor_active = False
        if agent_process and agent_process.poll() is None:
            try:
                agent_process.terminate()
                agent_process.wait(timeout=3)
            except:
                agent_process.kill()
        agent_process = None
        agent_stdin = None

    def _monitor_stdout(self):
        global agent_connected
        while monitor_active and agent_process and agent_process.poll() is None:
            try:
                line = agent_process.stdout.readline()
                if not line:
                    break

                # Check for JSON messages from agent
                if line.startswith('{') and 'stdin_result' in line:
                    try:
                        msg = json.loads(line.strip())
                        cmd = msg.get('command')
                        ok = msg.get('ok', False)
                        if cmd == 'print_ticket':
                            self.root.after(0, lambda ok=ok: (
                                self._log("✅ Ticket impreso correctamente", GREEN) if ok
                                else self._log(f"❌ Error ticket: {msg.get('error', 'desconocido')}", RED)
                            ))
                        elif cmd == 'open_drawer':
                            self.root.after(0, lambda ok=ok: (
                                self._log("✅ Cajón abierto", GREEN) if ok
                                else self._log(f"❌ Error cajón: {msg.get('error', 'desconocido')}", RED)
                            ))
                        elif cmd == 'status':
                            connected = msg.get('connected', False)
                            self.root.after(0, lambda c=connected: (
                                self._set_status("Conectado ✅", GREEN, GREEN) if c
                                else self._set_status("Desconectado", TEXT_MUTED, GRAY)
                            ))
                    except:
                        pass
                elif '✅ Authenticated' in line or 'auth_ok' in line:
                    agent_connected = True
                    self.root.after(0, lambda: self._set_status("Conectado ✅", GREEN, GREEN))
                    self.root.after(0, lambda: self._log("✅ Autenticado en el servidor", GREEN))
                    self.root.after(0, lambda: self.acc_name.config(text="TechExpert"))
                    self.root.after(0, lambda: self.acc_user.config(text="Admin — Agente conectado"))
                elif '❌' in line:
                    self.root.after(0, lambda: self._log(f"⚠️ {line.strip()}", RED))
                elif '🔐' in line:
                    self.root.after(0, lambda: self._log(f"🔐 {line.strip()}", PRIMARY_BLUE))
                elif '✅ Connected' in line:
                    self.root.after(0, lambda: self._set_status("Conectando...", PRIMARY_BLUE, PRIMARY_BLUE))
                    self.root.after(0, lambda: self._log("🔌 Conectado al túnel", PRIMARY_BLUE))
                elif 'startup' in line:
                    pass  # skip initial logs
                else:
                    # Show other agent output
                    stripped = line.strip()
                    if stripped and not stripped.startswith('[') and len(stripped) > 3:
                        self.root.after(0, lambda s=stripped: self._log(f"📡 {s}", TEXT_MUTED))
            except:
                break

        # Process ended
        if monitor_active:
            global agent_connected
            agent_connected = False
            self.root.after(0, lambda: self._set_status("Desconectado", TEXT_MUTED, GRAY))
            self.root.after(0, lambda: self._log("⚠️ Proceso del agente terminado", RED))
            self.root.after(0, lambda: self._switch_to_disconnected())

    def _send_command(self, command_obj):
        global agent_stdin
        if not agent_stdin:
            self._log("❌ Agente no iniciado", RED)
            return
        cmd_str = json.dumps(command_obj) + '\n'
        with stdin_cmd_lock:
            try:
                agent_stdin.write(cmd_str)
                agent_stdin.flush()
            except Exception as e:
                self._log(f"❌ Error enviando comando: {e}", RED)

    # ── UI Actions ──

    def do_connect(self):
        token = self.token_entry.get().strip()
        if not token:
            self._log("❌ Token vacío", RED)
            return

        self.token = token
        self.connect_btn.config(text="Conectando...", state=tk.DISABLED, bg=TEXT_MUTED)
        self._set_status("Conectando...", PRIMARY_BLUE, PRIMARY_BLUE)
        self._log(f"🔑 Token: {token[:16]}...")

        threading.Thread(target=self._connect_worker, args=(token,), daemon=True).start()

    def _connect_worker(self, token):
        ok = self._start_agent_process(token)
        if ok:
            self.root.after(0, lambda: self._switch_to_connected())
            self.root.after(0, lambda: self._set_status("Conectando...", PRIMARY_BLUE, PRIMARY_BLUE))
            # Give agent time to connect
            time.sleep(3)
            self.root.after(0, lambda: self.connect_btn.config(text="✅ Conectado", state=tk.NORMAL, bg=GREEN))

    def _switch_to_connected(self):
        self.token_section.pack_forget()
        self.connected_section.pack(fill=tk.X)

    def _switch_to_disconnected(self):
        self.connected_section.pack_forget()
        self.token_section.pack(fill=tk.X)
        self.connect_btn.config(text="Conectar", state=tk.NORMAL, bg=PRIMARY_BLUE)
        self.acc_name.config(text="TechExpert")
        self.acc_user.config(text="Agente desconectado")
        self.printer_label.config(text="")

    def do_disconnect(self):
        self._stop_agent_process()
        agent_connected = False
        self._set_status("Desconectado", TEXT_MUTED, GRAY)
        self._log("❌ Desconectado", RED)
        self._switch_to_disconnected()

    def do_test_print(self):
        self._log("🖨️ Enviando ticket de prueba...", PRIMARY_BLUE)
        self._send_command({"command": "print_ticket", "text": "🧾 TEST TICKET\nTechExpert TPV\n\nImpresora configurada correctamente\nFecha: " + time.strftime("%d/%m/%Y %H:%M")})

    def do_open_drawer(self):
        self._log("💰 Abriendo cajón...", PRIMARY_BLUE)
        self._send_command({"command": "open_drawer"})

    def do_get_status(self):
        self._log("🔍 Solicitando estado...", PRIMARY_BLUE)
        self._send_command({"command": "status"})

    def on_close(self):
        self._stop_agent_process()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    app = TechExpertApp()
    app.run()

if __name__ == '__main__':
    main()
