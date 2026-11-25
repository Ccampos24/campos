import customtkinter as ctk
from tkinter import filedialog, messagebox, TclError
from PIL import Image, ImageTk
import os
import sys
import time
import shutil
import json
import uuid
import hashlib
import threading
import webbrowser
import winreg
from datetime import datetime, timedelta
from app_storage import get_app_data_dir, migrate_legacy_app_data
from cloud_account import CloudAccountClient, CloudAccountError

# Configuração global do tema escuro
ctk.set_appearance_mode("dark")


def resource_path(relative_path):
    """Retorna o caminho absoluto para recursos (funciona tanto em .py quanto empacotado em .exe)."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class CamposDefenserApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configurações da Janela Principal
        self.title("Campos Defenser — Campos Tecnologia")
        self.geometry("1040x660")
        self.resizable(False, False)
        self.configure(fg_color="#090C15")

        self.cloud_client = CloudAccountClient()
        self.account_session = None
        self.account_email = None
        self.account_user_id = None
        self.checking_payment = False

        # Aplicar Logo como Favicon / Ícone da Janela e Barra de Tarefas
        self.setup_window_icon()

        # Diretórios e Bancos Locais (JSON)
        self.app_data_dir = get_app_data_dir()
        legacy_app_data_dir = os.path.join(os.path.abspath("."), "CamposDefenser_Data")
        migrate_legacy_app_data(legacy_app_data_dir, self.app_data_dir)
        self.vault_dir = os.path.join(self.app_data_dir, "quarantine_vault")
        os.makedirs(self.vault_dir, exist_ok=True)

        self.quarantine_db_file = os.path.join(self.app_data_dir, "quarantine.json")
        self.history_db_file = os.path.join(self.app_data_dir, "history.json")
        self.settings_db_file = os.path.join(self.app_data_dir, "settings.json")
        self.license_db_file = os.path.join(self.app_data_dir, "license.json")

        # Carregar Configurações e Licença
        self.settings = self.load_settings()
        self.license_data = self.load_license()

        # Banco de Assinaturas Maliciosas (SHA-256)
        self.malware_hashes = {
            "275A021BBFB6489E54D471899F7DB9D1663FC695EC2FE2A2C4538AABF651FD0F": "EICAR-Test-File (Ameaça Padrão de Teste)",
            "44D88612FEA8A8F36DE82E1278ABB02F": "EICAR-MD5-Signature"
        }
        self.db_version = self.settings.get("db_version", "v2026.11.24")

        # Estados do Sistema
        self.is_scanning = False
        self.detected_threats = []
        self.known_files_state = {}

        # Layout Principal (Sidebar + Área de Conteúdo)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ==========================================================
        # MENU LATERAL (IDENTIDADE CAMPOS DEFENSER)
        # ==========================================================
        self.sidebar = ctk.CTkFrame(self, width=260, corner_radius=0, fg_color="#06080F")
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        logo_file = resource_path("logo.png")
        if os.path.exists(logo_file):
            img_data = Image.open(logo_file)
            self.logo_img = ctk.CTkImage(light_image=img_data, dark_image=img_data, size=(120, 120))
            self.logo_label = ctk.CTkLabel(self.sidebar, image=self.logo_img, text="")
            self.logo_label.pack(pady=(18, 6))

        ctk.CTkLabel(
            self.sidebar,
            text="CAMPOS DEFENSER",
            font=("Segoe UI", 17, "bold"),
            text_color="#FFFFFF"
        ).pack()

        ctk.CTkLabel(
            self.sidebar,
            text="Campos Tecnologia",
            font=("Segoe UI", 12, "bold"),
            text_color="#00E5FF"
        ).pack(pady=(2, 12))

        # Badge de Status da Assinatura no Menu Lateral
        self.lbl_sidebar_license = ctk.CTkLabel(
            self.sidebar,
            text="Carregando licença...",
            font=("Segoe UI", 11, "bold"),
            fg_color="#131B2E",
            text_color="#00FF88",
            corner_radius=6,
            height=30
        )
        self.lbl_sidebar_license.pack(fill="x", padx=20, pady=(0, 12))

        ctk.CTkFrame(self.sidebar, height=1, fg_color="#141E30").pack(fill="x", padx=22, pady=(0, 10))

        # Botões de Navegação
        self.menu_buttons = {}
        menu_items = [
            ("dashboard", "🛡️  Painel Principal"),
            ("scan", "🔍  Verificação"),
            ("protection", "⚡  Proteção em Tempo Real"),
            ("quarantine", "🔒  Quarentena"),
            ("history", "📜  Histórico"),
            ("plans", "👑  Planos & Assinatura"),
            ("settings", "⚙️  Configurações")
        ]

        for key, label in menu_items:
            btn = ctk.CTkButton(
                self.sidebar,
                text=label,
                font=("Segoe UI", 13, "bold"),
                height=39,
                corner_radius=8,
                anchor="w",
                fg_color="transparent",
                text_color="#A0B2C6",
                hover_color="#131B2E",
                command=lambda k=key: self.show_screen(k)
            )
            btn.pack(fill="x", padx=16, pady=3)
            self.menu_buttons[key] = btn

        # Rodapé do Menu Lateral
        ctk.CTkLabel(
            self.sidebar,
            text="Sua segurança digital\nsempre protegida",
            font=("Segoe UI", 10),
            text_color="#526480"
        ).pack(side="bottom", pady=12)

        # ==========================================================
        # ÁREA DE CONTEÚDO PRINCIPAL
        # ==========================================================
        self.main_area = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_area.grid(row=0, column=1, sticky="nsew", padx=35, pady=28)
        self.main_area.grid_columnconfigure(0, weight=1)
        self.main_area.grid_rowconfigure(0, weight=1)

        self.screens = {}
        self.create_dashboard_screen()
        self.create_scan_screen()
        self.create_protection_screen()
        self.create_quarantine_screen()
        self.create_history_screen()
        self.create_plans_screen()
        self.create_settings_screen()
        self.update_account_ui()

        # Atualiza o status da licença e abre a tela apropriada
        self.update_license_ui()
        if self.is_license_valid():
            self.show_screen("dashboard")
        else:
            self.show_screen("plans")

        # Inicia o Escudo em Tempo Real em segundo plano
        threading.Thread(target=self.realtime_monitor_loop, daemon=True).start()

        # Inicia verificador periódico de expiração da licença
        self.monitor_license_expiration()

    # ==========================================================
    # GESTÃO DE LICENÇA E 1 DIA GRÁTIS (TRIAL 24H)
    # ==========================================================
    def load_license(self):
        now = datetime.now()
        if os.path.exists(self.license_db_file):
            try:
                with open(self.license_db_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        # Primeira execução: concede 1 dia grátis (24 horas exatas)
        expires = now + timedelta(days=1)
        data = {
            "status": "trial",
            "plan_name": "Teste Grátis (1 Dia)",
            "started_at": now.isoformat(),
            "expires_at": expires.isoformat()
        }
        self.save_license(data)
        return data

    def save_license(self, data=None):
        if data is not None:
            self.license_data = data
        with open(self.license_db_file, "w", encoding="utf-8") as f:
            json.dump(self.license_data, f, indent=4, ensure_ascii=False)

    def is_license_valid(self):
        try:
            account_user_id = self.license_data.get("account_user_id")
            if account_user_id and account_user_id != self.account_user_id:
                return False
            expires_at = datetime.fromisoformat(self.license_data["expires_at"])
            now = datetime.now(expires_at.tzinfo) if expires_at.tzinfo else datetime.now()
            return now < expires_at
        except Exception:
            return False

    def get_remaining_time_text(self):
        try:
            expires_at = datetime.fromisoformat(self.license_data["expires_at"])
            now = datetime.now(expires_at.tzinfo) if expires_at.tzinfo else datetime.now()
            diff = expires_at - now
            if diff.total_seconds() <= 0:
                return "Expirado"
            days = diff.days
            hours, remainder = divmod(diff.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            if days > 0:
                return f"{days}d {hours}h restantes"
            return f"{hours}h {minutes}m restantes"
        except Exception:
            return "Expirado"

    def update_license_ui(self):
        valid = self.is_license_valid()
        remaining = self.get_remaining_time_text()
        plan_name = self.license_data.get("plan_name", "Teste Grátis")

        if valid:
            is_trial = self.license_data.get("status") == "trial"
            badge_color = "#00E5FF" if is_trial else "#00FF88"
            self.lbl_sidebar_license.configure(
                text=f"👑 {plan_name}\n({remaining})",
                text_color=badge_color
            )
            if hasattr(self, "lbl_plans_status"):
                self.lbl_plans_status.configure(
                    text=f"✅ Licença Ativa: {plan_name} • Tempo restante: {remaining}",
                    text_color="#00FF88"
                )
        else:
            self.lbl_sidebar_license.configure(
                text="⚠️ ASSINATURA EXPIRADA\nClique para assinar",
                text_color="#FF4C4C"
            )
            if hasattr(self, "lbl_plans_status"):
                self.lbl_plans_status.configure(
                    text="🔒 Seu período de 1 dia grátis terminou. Escolha um plano abaixo para liberar após o pagamento!",
                    text_color="#FF4C4C"
                )

    def update_account_ui(self):
        if not hasattr(self, "btn_account"):
            return
        if self.account_email:
            self.btn_account.configure(text="Conta conectada")
        else:
            self.btn_account.configure(text="Entrar / Criar conta")

    @staticmethod
    def set_account_status(status_label, text, color):
        try:
            if status_label.winfo_exists():
                status_label.configure(text=text, text_color=color)
        except TclError:
            pass

    def open_account_modal(self):
        modal = ctk.CTkToplevel(self)
        modal.title("Conta Campos Defenser")
        modal.geometry("440x390")
        modal.resizable(False, False)
        modal.configure(fg_color="#090C15")
        modal.transient(self)
        modal.grab_set()

        ctk.CTkLabel(
            modal,
            text="Sua conta e seu plano",
            font=("Segoe UI", 20, "bold"),
            text_color="#00E5FF"
        ).pack(pady=(22, 6))
        ctk.CTkLabel(
            modal,
            text="Entre ou crie uma conta para recuperar seu plano em reinstalações.",
            font=("Segoe UI", 12),
            text_color="#A0B2C6",
            wraplength=380
        ).pack(pady=(0, 14))

        entry_email = ctk.CTkEntry(
            modal,
            placeholder_text="E-mail",
            width=360,
            height=38
        )
        entry_email.pack(pady=5)

        entry_password = ctk.CTkEntry(
            modal,
            placeholder_text="Senha (mínimo 8 caracteres)",
            show="*",
            width=360,
            height=38
        )
        entry_password.pack(pady=5)

        status_label = ctk.CTkLabel(
            modal,
            text=self.cloud_client.config_error or "",
            font=("Segoe UI", 11),
            text_color="#FFB020",
            wraplength=380
        )
        status_label.pack(pady=(10, 4))

        def start_auth(operation):
            email = entry_email.get().strip()
            password = entry_password.get()
            if "@" not in email:
                messagebox.showwarning("E-mail inválido", "Informe um e-mail válido.")
                return
            if len(password) < 8:
                messagebox.showwarning("Senha inválida", "A senha deve ter pelo menos 8 caracteres.")
                return

            status_label.configure(text="Conectando à conta online...", text_color="#00E5FF")
            threading.Thread(
                target=self.account_auth_worker,
                args=(operation, email, password, status_label),
                daemon=True
            ).start()

        buttons = ctk.CTkFrame(modal, fg_color="transparent")
        buttons.pack(fill="x", padx=35, pady=(8, 0))
        ctk.CTkButton(
            buttons,
            text="Entrar",
            command=lambda: start_auth("sign_in"),
            width=150
        ).pack(side="left", padx=5, expand=True)
        ctk.CTkButton(
            buttons,
            text="Criar conta",
            command=lambda: start_auth("sign_up"),
            width=150,
            fg_color="#131B2E",
            text_color="#00E5FF",
            border_color="#00E5FF",
            border_width=1
        ).pack(side="left", padx=5, expand=True)

        ctk.CTkButton(
            modal,
            text="Esqueci minha senha",
            command=lambda: self.request_password_reset(entry_email.get().strip(), status_label),
            width=180,
            fg_color="transparent",
            hover_color="#131B2E",
            text_color="#00E5FF"
        ).pack(pady=(8, 0))
        ctk.CTkButton(
            modal,
            text="Sair da conta",
            command=self.sign_out_account,
            width=150,
            fg_color="transparent",
            hover_color="#131B2E",
            text_color="#A0B2C6"
        ).pack(pady=(12, 0))

    def request_password_reset(self, email, status_label):
        if "@" not in email:
            messagebox.showwarning("E-mail inválido", "Informe seu e-mail para receber o link de redefinição.")
            return
        status_label.configure(text="Solicitando redefinição de senha...", text_color="#00E5FF")
        threading.Thread(
            target=self.password_reset_worker,
            args=(email, status_label),
            daemon=True
        ).start()

    def password_reset_worker(self, email, status_label):
        try:
            self.cloud_client.reset_password(email)
            message = "Se a conta existir, você receberá um e-mail para redefinir a senha."
            color = "#00FF88"
        except CloudAccountError as exc:
            message = str(exc)
            color = "#FF4C4C"
        self.after(0, lambda: self.set_account_status(status_label, message, color))

    def account_auth_worker(self, operation, email, password, status_label):
        try:
            if operation == "sign_up":
                session, _ = self.cloud_client.sign_up(email, password)
                if session is None:
                    self.after(0, lambda: self.set_account_status(
                        status_label,
                        "Conta criada. Confirme o e-mail recebido e depois entre.",
                        "#00FF88"
                    ))
                    return
            else:
                session = self.cloud_client.sign_in(email, password)
            self.after(0, lambda: self.finish_account_sign_in(session, status_label))
        except CloudAccountError as exc:
            error = str(exc)
            self.after(0, lambda: self.set_account_status(status_label, error, "#FF4C4C"))

    def finish_account_sign_in(self, session, status_label):
        if not session.get("user_id"):
            status_label.configure(text="A conta não retornou um identificador válido.", text_color="#FF4C4C")
            return
        self.account_session = session
        self.account_email = session.get("email")
        self.account_user_id = session["user_id"]
        self.update_account_ui()
        status_label.configure(text="Conta conectada. Sincronizando plano...", text_color="#00E5FF")
        threading.Thread(
            target=self.sync_account_plan_worker,
            args=(session, status_label),
            daemon=True
        ).start()

    def sync_account_plan_worker(self, session, status_label=None, payment_id=None):
        try:
            result = self.cloud_client.sync_plan(session, payment_id)
            plan = result.get("plan")
            if not plan:
                raise CloudAccountError("A conta não possui um plano cadastrado no servidor.")
            user_id = session["user_id"]
            self.after(0, lambda: self.apply_cloud_plan(plan, user_id))
            if status_label is not None:
                self.after(0, lambda: self.set_account_status(
                    status_label, "Plano sincronizado com a conta.", "#00FF88"
                ))
        except CloudAccountError as exc:
            error = str(exc)
            if status_label is not None:
                self.after(0, lambda: self.set_account_status(status_label, error, "#FF4C4C"))

    def apply_cloud_plan(self, plan, expected_user_id):
        if not self.account_user_id or self.account_user_id != expected_user_id:
            return
        self.save_license({
            "status": plan["status"],
            "plan_name": plan["plan_name"],
            "started_at": plan["started_at"],
            "expires_at": plan["expires_at"],
            "account_user_id": self.account_user_id,
            "account_email": self.account_email
        })
        self.update_license_ui()
        if self.is_license_valid():
            self.show_screen("dashboard")
        else:
            self.show_screen("plans")

    def sign_out_account(self):
        self.checking_payment = False
        self.account_session = None
        self.account_email = None
        self.account_user_id = None
        self.update_account_ui()
        self.update_license_ui()
        if self.license_data.get("account_user_id"):
            self.show_screen("plans")

    def monitor_license_expiration(self):
        self.update_license_ui()
        if not self.is_license_valid():
            self.show_screen("plans")
        self.after(30000, self.monitor_license_expiration)

    # ==========================================================
    # INICIALIZAÇÃO AUTOMÁTICA COM O WINDOWS (REGISTRO)
    # ==========================================================
    def is_windows_startup_enabled(self):
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_READ
            )
            winreg.QueryValueEx(key, "CamposDefenser")
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            return False
        except Exception:
            return False

    def set_windows_startup(self, enable: bool):
        reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "CamposDefenser"

        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                reg_path,
                0,
                winreg.KEY_SET_VALUE
            )
            if enable:
                if getattr(sys, "frozen", False):
                    cmd = f'"{sys.executable}"'
                else:
                    python_dir = os.path.dirname(sys.executable)
                    pythonw = os.path.join(python_dir, "pythonw.exe")
                    if not os.path.exists(pythonw):
                        pythonw = sys.executable
                    script_path = os.path.abspath(__file__)
                    cmd = f'"{pythonw}" "{script_path}"'

                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
            return True
        except Exception as e:
            messagebox.showerror("Erro de Permissão", f"Não foi possível alterar a inicialização do Windows:\n{e}")
            return False

    # ==========================================================
    # CONFIGURAÇÃO DO FAVICON / ÍCONE DO WINDOWS
    # ==========================================================
    def setup_window_icon(self):
        logo_png = resource_path("logo.png")
        logo_ico = os.path.join(os.path.abspath("."), "logo.ico")

        try:
            if os.path.exists(logo_png):
                img = Image.open(logo_png)
                if not os.path.exists(logo_ico):
                    img.save(
                        logo_ico,
                        format="ICO",
                        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
                    )
                if os.path.exists(logo_ico):
                    self.iconbitmap(logo_ico)
                self._icon_photo = ImageTk.PhotoImage(img.resize((64, 64)))
                self.wm_iconphoto(True, self._icon_photo)
        except Exception:
            pass

    # ==========================================================
    # PERSISTÊNCIA DE DADOS (JSON)
    # ==========================================================
    def load_json(self, filepath):
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def save_json(self, filepath, data):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def load_settings(self):
        default_downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        if not os.path.exists(default_downloads):
            default_downloads = os.getcwd()

        defaults = {
            "realtime_active": True,
            "auto_quarantine": True,
            "heuristic_scan": True,
            "start_with_windows": self.is_windows_startup_enabled(),
            "monitored_folder": default_downloads,
            "db_version": "v2026.11.24"
        }
        if os.path.exists(self.settings_db_file):
            try:
                with open(self.settings_db_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    defaults.update(loaded)
            except Exception:
                pass
        defaults["start_with_windows"] = self.is_windows_startup_enabled()
        return defaults

    def save_settings(self):
        with open(self.settings_db_file, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, indent=4, ensure_ascii=False)

    # ==========================================================
    # TELA 1: PAINEL PRINCIPAL (DASHBOARD)
    # ==========================================================
    def create_dashboard_screen(self):
        frame = ctk.CTkFrame(self.main_area, fg_color="transparent")

        self.dash_card = ctk.CTkFrame(
            frame,
            fg_color="#0E1525",
            border_color="#00E5FF",
            border_width=1,
            corner_radius=16
        )
        self.dash_card.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.94, relheight=0.84)

        logo_file = resource_path("logo.png")
        if os.path.exists(logo_file):
            img_data = Image.open(logo_file)
            self.dash_logo = ctk.CTkImage(light_image=img_data, dark_image=img_data, size=(90, 90))
            ctk.CTkLabel(self.dash_card, image=self.dash_logo, text="").pack(pady=(25, 8))
        else:
            ctk.CTkLabel(self.dash_card, text="🛡️", font=("Segoe UI", 48)).pack(pady=(30, 5))

        self.dash_title = ctk.CTkLabel(
            self.dash_card,
            text="SEU COMPUTADOR ESTÁ PROTEGIDO",
            font=("Segoe UI", 22, "bold"),
            text_color="#00E5FF"
        )
        self.dash_title.pack()

        self.dash_subtitle = ctk.CTkLabel(
            self.dash_card,
            text="Sua segurança digital sempre protegida • Campos Tecnologia",
            font=("Segoe UI", 13),
            text_color="#A0B2C6"
        )
        self.dash_subtitle.pack(pady=(5, 24))

        quick_btns = ctk.CTkFrame(self.dash_card, fg_color="transparent")
        quick_btns.pack()

        ctk.CTkButton(
            quick_btns,
            text="🔍  VERIFICAÇÃO RÁPIDA",
            font=("Segoe UI", 13, "bold"),
            fg_color="#00E5FF",
            text_color="#050811",
            hover_color="#33ECFF",
            height=44,
            width=210,
            corner_radius=8,
            command=self.run_quick_system_scan
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            quick_btns,
            text="📁  VERIFICAR PASTA",
            font=("Segoe UI", 13, "bold"),
            fg_color="#131B2E",
            text_color="#00E5FF",
            border_color="#00E5FF",
            border_width=1,
            hover_color="#1C2844",
            height=44,
            width=210,
            corner_radius=8,
            command=lambda: self.show_screen("scan")
        ).pack(side="left", padx=8)

        info_frame = ctk.CTkFrame(self.dash_card, fg_color="#090D18", corner_radius=10)
        info_frame.pack(side="bottom", fill="x", padx=30, pady=22)
        info_frame.grid_columnconfigure((0, 1, 2), weight=1)

        col1 = ctk.CTkFrame(info_frame, fg_color="transparent")
        col1.grid(row=0, column=0, pady=12)
        ctk.CTkLabel(col1, text="ESCUDO EM TEMPO REAL", font=("Segoe UI", 10, "bold"), text_color="#6C7E96").pack()
        self.dash_shield_status = ctk.CTkLabel(col1, text="ATIVADO", font=("Segoe UI", 13, "bold"), text_color="#00FF88")
        self.dash_shield_status.pack()

        col2 = ctk.CTkFrame(info_frame, fg_color="transparent")
        col2.grid(row=0, column=1, pady=12)
        ctk.CTkLabel(col2, text="MOTOR DE DETECÇÃO", font=("Segoe UI", 10, "bold"), text_color="#6C7E96").pack()
        ctk.CTkLabel(col2, text="SHA-256 + Heurística", font=("Segoe UI", 13, "bold"), text_color="#FFFFFF").pack()

        col3 = ctk.CTkFrame(info_frame, fg_color="transparent")
        col3.grid(row=0, column=2, pady=12)
        ctk.CTkLabel(col3, text="ASSINATURAS", font=("Segoe UI", 10, "bold"), text_color="#6C7E96").pack()
        self.dash_db_label = ctk.CTkLabel(col3, text=f"Atualizado ({self.db_version})", font=("Segoe UI", 13, "bold"), text_color="#00FF88")
        self.dash_db_label.pack()

        self.screens["dashboard"] = frame

    def run_quick_system_scan(self):
        if not self.is_license_valid():
            self.show_screen("plans")
            return
        self.show_screen("scan")
        if self.is_scanning:
            return
        targets = [
            os.path.join(os.path.expanduser("~"), "Downloads"),
            os.path.join(os.path.expanduser("~"), "Desktop")
        ]
        files_to_scan = []
        for folder in targets:
            if os.path.exists(folder):
                for root, _, files in os.walk(folder):
                    for f in files:
                        files_to_scan.append(os.path.join(root, f))
        threading.Thread(
            target=self.run_scan,
            args=(files_to_scan, "Verificação Rápida (Downloads + Área de Trabalho)"),
            daemon=True
        ).start()

    # ==========================================================
    # TELA 2: VERIFICAÇÃO (SCANNER SHA-256 + HEURÍSTICA)
    # ==========================================================
    def create_scan_screen(self):
        frame = ctk.CTkFrame(self.main_area, fg_color="transparent")

        ctk.CTkLabel(frame, text="Verificação de Segurança", font=("Segoe UI", 24, "bold"), text_color="#FFFFFF").pack(anchor="w")
        ctk.CTkLabel(frame, text="Analise pastas, arquivos individuais ou execute uma varredura rápida nas áreas críticas.", font=("Segoe UI", 13), text_color="#A0B2C6").pack(anchor="w", pady=(2, 18))

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, 18))

        self.btn_scan_folder = ctk.CTkButton(
            btn_row,
            text="📁  Verificar Pasta",
            font=("Segoe UI", 13, "bold"),
            fg_color="#00E5FF",
            text_color="#050811",
            hover_color="#33ECFF",
            height=42,
            width=165,
            corner_radius=8,
            command=self.select_folder_and_scan
        )
        self.btn_scan_folder.pack(side="left", padx=(0, 10))

        self.btn_scan_file = ctk.CTkButton(
            btn_row,
            text="📄  Verificar Arquivo",
            font=("Segoe UI", 13, "bold"),
            fg_color="#131B2E",
            text_color="#00E5FF",
            border_color="#00E5FF",
            border_width=1,
            hover_color="#1C2844",
            height=42,
            width=165,
            corner_radius=8,
            command=self.select_file_and_scan
        )
        self.btn_scan_file.pack(side="left", padx=(0, 10))

        self.btn_quarantine_threats = ctk.CTkButton(
            btn_row,
            text="🔒  Isolar Ameaças",
            font=("Segoe UI", 13, "bold"),
            fg_color="#FF4C4C",
            text_color="#FFFFFF",
            hover_color="#FF6B6B",
            height=42,
            width=170,
            corner_radius=8,
            state="disabled",
            command=self.quarantine_detected_threats
        )
        self.btn_quarantine_threats.pack(side="right")

        self.lbl_scan_status = ctk.CTkLabel(frame, text="Pronto para iniciar a verificação.", font=("Segoe UI", 13, "bold"), text_color="#00E5FF")
        self.lbl_scan_status.pack(anchor="w", pady=(4, 6))

        self.progress_bar = ctk.CTkProgressBar(frame, height=12, corner_radius=6, fg_color="#131B2E", progress_color="#00E5FF")
        self.progress_bar.pack(fill="x", pady=(0, 18))
        self.progress_bar.set(0)

        ctk.CTkLabel(frame, text="Relatório de Análise:", font=("Segoe UI", 13, "bold"), text_color="#FFFFFF").pack(anchor="w", pady=(0, 6))
        self.txt_scan_log = ctk.CTkTextbox(
            frame,
            fg_color="#0E1525",
            text_color="#E2E8F0",
            border_color="#1A263D",
            border_width=1,
            corner_radius=10,
            font=("Consolas", 12)
        )
        self.txt_scan_log.pack(fill="both", expand=True)
        self.txt_scan_log.insert("end", "Aguardando seleção de alvo para varredura...\n")
        self.txt_scan_log.configure(state="disabled")

        self.screens["scan"] = frame

    def select_folder_and_scan(self):
        if not self.is_license_valid():
            self.show_screen("plans")
            return
        if self.is_scanning:
            return
        folder = filedialog.askdirectory(title="Selecione a pasta para verificar")
        if folder:
            files_to_scan = []
            for root, _, files in os.walk(folder):
                for f in files:
                    files_to_scan.append(os.path.join(root, f))
            threading.Thread(target=self.run_scan, args=(files_to_scan, folder), daemon=True).start()

    def select_file_and_scan(self):
        if not self.is_license_valid():
            self.show_screen("plans")
            return
        if self.is_scanning:
            return
        file_path = filedialog.askopenfilename(title="Selecione o arquivo para verificar")
        if file_path:
            threading.Thread(target=self.run_scan, args=([file_path], file_path), daemon=True).start()

    def log_message(self, message):
        self.txt_scan_log.configure(state="normal")
        self.txt_scan_log.insert("end", message + "\n")
        self.txt_scan_log.see("end")
        self.txt_scan_log.configure(state="disabled")

    def calculate_sha256(self, filepath):
        sha256_hash = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                for byte_block in iter(lambda: f.read(65536), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest().upper()
        except Exception:
            return None

    def analyze_file(self, filepath):
        file_hash = self.calculate_sha256(filepath)
        if file_hash and file_hash in self.malware_hashes:
            return self.malware_hashes[file_hash], file_hash

        if self.settings.get("heuristic_scan", True):
            lower_name = os.path.basename(filepath).lower()
            suspicious_double_exts = [".pdf.exe", ".docx.exe", ".jpg.exe", ".png.exe", ".txt.exe", ".vbs.exe", ".bat.exe"]
            for ext in suspicious_double_exts:
                if lower_name.endswith(ext):
                    return "Heurística: Extensão Dupla Suspeita (Trojan.Disguise)", file_hash or "N/A"

        return None, file_hash

    def run_scan(self, files, target_name):
        self.is_scanning = True
        self.detected_threats = []
        self.btn_scan_folder.configure(state="disabled")
        self.btn_scan_file.configure(state="disabled")
        self.btn_quarantine_threats.configure(state="disabled")

        self.txt_scan_log.configure(state="normal")
        self.txt_scan_log.delete("1.0", "end")
        self.txt_scan_log.configure(state="disabled")
        self.progress_bar.set(0)

        total = len(files)
        if total == 0:
            self.lbl_scan_status.configure(text="Nenhum arquivo encontrado no local selecionado.", text_color="#A0B2C6")
            self.is_scanning = False
            self.btn_scan_folder.configure(state="normal")
            self.btn_scan_file.configure(state="normal")
            return

        for idx, filepath in enumerate(files, start=1):
            filename = os.path.basename(filepath)
            self.lbl_scan_status.configure(text=f"Analisando ({idx}/{total}): {filename}", text_color="#00E5FF")
            self.progress_bar.set(idx / total)

            threat_name, file_hash = self.analyze_file(filepath)
            if threat_name:
                self.detected_threats.append({
                    "path": filepath,
                    "threat": threat_name,
                    "hash": file_hash
                })
                self.log_message(f"[🚨 AMEAÇA DETECTADA] {threat_name}\n    Local: {filepath}\n    SHA-256: {file_hash}\n")

        threats_count = len(self.detected_threats)
        if threats_count > 0:
            self.lbl_scan_status.configure(text=f"⚠️ Verificação concluída: {threats_count} ameaça(s) encontrada(s)!", text_color="#FF4C4C")
            self.log_message(f"--- RESUMO: {total} arquivo(s) analisado(s) | {threats_count} ameaça(s) detectada(s). ---")
            self.btn_quarantine_threats.configure(state="normal")
        else:
            self.lbl_scan_status.configure(text=f"✅ Verificação concluída: {total} arquivo(s) limpo(s)!", text_color="#00FF88")
            self.log_message(f"✅ Nenhuma ameaça encontrada.\n--- RESUMO: {total} arquivo(s) analisado(s) com segurança. ---")

        history = self.load_json(self.history_db_file)
        history.insert(0, {
            "date": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "target": target_name,
            "scanned": total,
            "threats": threats_count
        })
        self.save_json(self.history_db_file, history)

        self.is_scanning = False
        self.btn_scan_folder.configure(state="normal")
        self.btn_scan_file.configure(state="normal")

    def move_single_file_to_quarantine(self, orig_path, threat_name):
        if not os.path.exists(orig_path):
            return False
        try:
            vault_filename = f"{uuid.uuid4().hex}.quarantine"
            vault_path = os.path.join(self.vault_dir, vault_filename)
            shutil.move(orig_path, vault_path)

            q_data = self.load_json(self.quarantine_db_file)
            q_data.insert(0, {
                "id": vault_filename,
                "original_name": os.path.basename(orig_path),
                "original_path": orig_path,
                "threat": threat_name,
                "date": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            })
            self.save_json(self.quarantine_db_file, q_data)
            return True
        except Exception:
            return False

    def quarantine_detected_threats(self):
        if not self.detected_threats:
            return

        moved_count = 0
        for item in self.detected_threats:
            if self.move_single_file_to_quarantine(item["path"], item["threat"]):
                moved_count += 1

        self.detected_threats = []
        self.btn_quarantine_threats.configure(state="disabled")
        self.log_message(f"\n🔒 {moved_count} ameaça(s) movida(s) com segurança para a Quarentena!")
        self.lbl_scan_status.configure(text="🛡️ Ameaças neutralizadas e isoladas na Quarentena.", text_color="#00FF88")

    # ==========================================================
    # TELA 3: PROTEÇÃO EM TEMPO REAL
    # ==========================================================
    def create_protection_screen(self):
        frame = ctk.CTkFrame(self.main_area, fg_color="transparent")

        ctk.CTkLabel(frame, text="Proteção em Tempo Real", font=("Segoe UI", 24, "bold"), text_color="#FFFFFF").pack(anchor="w")
        ctk.CTkLabel(frame, text="Monitoramento contínuo de novos arquivos baixados ou criados na pasta vigiada.", font=("Segoe UI", 13), text_color="#A0B2C6").pack(anchor="w", pady=(2, 18))

        control_card = ctk.CTkFrame(frame, fg_color="#0E1525", border_color="#1A263D", border_width=1, corner_radius=12)
        control_card.pack(fill="x", pady=(0, 15))

        top_row = ctk.CTkFrame(control_card, fg_color="transparent")
        top_row.pack(fill="x", padx=20, pady=15)

        self.switch_realtime = ctk.CTkSwitch(
            top_row,
            text="Escudo Ativo em Segundo Plano",
            font=("Segoe UI", 15, "bold"),
            text_color="#00FF88",
            progress_color="#00E5FF",
            command=self.toggle_realtime_shield
        )
        if self.settings.get("realtime_active", True):
            self.switch_realtime.select()
        else:
            self.switch_realtime.deselect()
        self.switch_realtime.pack(side="left")

        ctk.CTkButton(
            top_row,
            text="Alterar Pasta Vigiada",
            font=("Segoe UI", 12, "bold"),
            fg_color="#131B2E",
            hover_color="#1E293B",
            height=34,
            command=self.change_monitored_folder
        ).pack(side="right")

        self.lbl_monitored_path = ctk.CTkLabel(
            control_card,
            text=f"📂 Pasta monitorada: {self.settings['monitored_folder']}",
            font=("Segoe UI", 12),
            text_color="#A0B2C6"
        )
        self.lbl_monitored_path.pack(anchor="w", padx=20, pady=(0, 15))

        ctk.CTkLabel(frame, text="Atividade do Escudo em Tempo Real:", font=("Segoe UI", 13, "bold"), text_color="#FFFFFF").pack(anchor="w", pady=(5, 6))
        self.txt_realtime_log = ctk.CTkTextbox(
            frame,
            fg_color="#0E1525",
            text_color="#E2E8F0",
            border_color="#1A263D",
            border_width=1,
            corner_radius=10,
            font=("Consolas", 12)
        )
        self.txt_realtime_log.pack(fill="both", expand=True)
        self.txt_realtime_log.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] ⚡ Escudo iniciado. Vigiando: {self.settings['monitored_folder']}\n")
        self.txt_realtime_log.configure(state="disabled")

        self.screens["protection"] = frame
        self.sync_shield_ui()

    def log_realtime(self, msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.txt_realtime_log.configure(state="normal")
        self.txt_realtime_log.insert("end", f"[{timestamp}] {msg}\n")
        self.txt_realtime_log.see("end")
        self.txt_realtime_log.configure(state="disabled")

    def sync_shield_ui(self):
        active = self.settings.get("realtime_active", True) and self.is_license_valid()
        if active:
            self.switch_realtime.configure(text_color="#00FF88")
            self.dash_title.configure(text="SEU COMPUTADOR ESTÁ PROTEGIDO", text_color="#00E5FF")
            self.dash_subtitle.configure(text="Sua segurança digital sempre protegida • Campos Tecnologia")
            self.dash_shield_status.configure(text="ATIVADO", text_color="#00FF88")
            self.dash_card.configure(border_color="#00E5FF")
        else:
            self.switch_realtime.configure(text_color="#FF4C4C")
            self.dash_title.configure(text="PROTEÇÃO EM TEMPO REAL PAUSADA", text_color="#FF4C4C")
            self.dash_subtitle.configure(text="Atenção: Ative o escudo ou renove sua assinatura para proteção ativa.")
            self.dash_shield_status.configure(text="DESATIVADO", text_color="#FF4C4C")
            self.dash_card.configure(border_color="#FF4C4C")

    def toggle_realtime_shield(self):
        if not self.is_license_valid():
            self.switch_realtime.deselect()
            self.show_screen("plans")
            return
        active = bool(self.switch_realtime.get())
        self.settings["realtime_active"] = active
        self.save_settings()
        self.sync_shield_ui()
        if active:
            self.log_realtime("⚡ Proteção em Tempo Real ATIVADA.")
        else:
            self.log_realtime("⚠️ Proteção em Tempo Real DESATIVADA pelo usuário.")

    def change_monitored_folder(self):
        folder = filedialog.askdirectory(title="Escolha a pasta para monitoramento contínuo")
        if folder:
            self.settings["monitored_folder"] = folder
            self.save_settings()
            self.known_files_state = {}
            self.lbl_monitored_path.configure(text=f"📂 Pasta monitorada: {folder}")
            self.log_realtime(f"📂 Pasta vigiada alterada para: {folder}")

    def realtime_monitor_loop(self):
        while True:
            monitored_dir = self.settings.get("monitored_folder", "")
            if self.settings.get("realtime_active", True) and self.is_license_valid() and os.path.exists(monitored_dir):
                try:
                    current_files = {}
                    for entry in os.scandir(monitored_dir):
                        if entry.is_file():
                            stat = entry.stat()
                            current_files[entry.path] = stat.st_mtime

                    for filepath, mtime in current_files.items():
                        if filepath not in self.known_files_state or self.known_files_state[filepath] != mtime:
                            self.known_files_state[filepath] = mtime
                            threat_name, _ = self.analyze_file(filepath)
                            if threat_name:
                                filename = os.path.basename(filepath)
                                self.log_realtime(f"🚨 AMEAÇA DETECTADA: {filename} ({threat_name})")
                                if self.settings.get("auto_quarantine", True):
                                    if self.move_single_file_to_quarantine(filepath, threat_name):
                                        self.log_realtime(f"🔒 {filename} foi movido automaticamente para a Quarentena!")
                                        self.after(0, lambda f=filename, t=threat_name: messagebox.showwarning(
                                            "Campos Defenser — Ameaça Bloqueada!",
                                            f"O Escudo em Tempo Real interceptou e isolou uma ameaça:\n\nArquivo: {f}\nAmeaça: {t}\nAção: Movido para a Quarentena."
                                        ))

                    self.known_files_state = {k: v for k, v in self.known_files_state.items() if k in current_files}
                except Exception:
                    pass
            time.sleep(1.5)

    # ==========================================================
    # TELA 4: QUARENTENA
    # ==========================================================
    def create_quarantine_screen(self):
        frame = ctk.CTkFrame(self.main_area, fg_color="transparent")

        ctk.CTkLabel(frame, text="Cofre de Quarentena", font=("Segoe UI", 24, "bold"), text_color="#FFFFFF").pack(anchor="w")
        ctk.CTkLabel(frame, text="Arquivos isolados aqui estão neutralizados e não podem ser executados no Windows.", font=("Segoe UI", 13), text_color="#A0B2C6").pack(anchor="w", pady=(2, 15))

        self.quarantine_scroll = ctk.CTkScrollableFrame(frame, fg_color="#0E1525", border_color="#1A263D", border_width=1, corner_radius=10)
        self.quarantine_scroll.pack(fill="both", expand=True)

        self.screens["quarantine"] = frame

    def refresh_quarantine_list(self):
        for widget in self.quarantine_scroll.winfo_children():
            widget.destroy()

        q_data = self.load_json(self.quarantine_db_file)
        if not q_data:
            ctk.CTkLabel(self.quarantine_scroll, text="🔒 Nenhum arquivo em quarentena no momento.", font=("Segoe UI", 13), text_color="#6C7E96").pack(pady=40)
            return

        for item in q_data:
            card = ctk.CTkFrame(self.quarantine_scroll, fg_color="#131B2E", corner_radius=8)
            card.pack(fill="x", padx=10, pady=6)

            info = ctk.CTkFrame(card, fg_color="transparent")
            info.pack(side="left", padx=15, pady=10)

            ctk.CTkLabel(info, text=f"🚨 {item['original_name']}  ({item['threat']})", font=("Segoe UI", 13, "bold"), text_color="#FF4C4C").pack(anchor="w")
            ctk.CTkLabel(info, text=f"Origem: {item['original_path']}  •  Isolado em: {item['date']}", font=("Segoe UI", 11), text_color="#A0B2C6").pack(anchor="w")

            actions = ctk.CTkFrame(card, fg_color="transparent")
            actions.pack(side="right", padx=15)

            ctk.CTkButton(
                actions, text="Restaurar", width=85, height=30, fg_color="#1E293B", hover_color="#334155",
                command=lambda i=item: self.restore_quarantine_item(i)
            ).pack(side="left", padx=5)

            ctk.CTkButton(
                actions, text="Excluir", width=85, height=30, fg_color="#991B1B", hover_color="#DC2626",
                command=lambda i=item: self.delete_quarantine_item(i)
            ).pack(side="left")

    def restore_quarantine_item(self, item):
        vault_path = os.path.join(self.vault_dir, item["id"])
        try:
            if os.path.exists(vault_path):
                os.makedirs(os.path.dirname(item["original_path"]), exist_ok=True)
                shutil.move(vault_path, item["original_path"])
            q_data = [x for x in self.load_json(self.quarantine_db_file) if x["id"] != item["id"]]
            self.save_json(self.quarantine_db_file, q_data)
            self.refresh_quarantine_list()
        except Exception as e:
            messagebox.showerror("Erro ao restaurar", str(e))

    def delete_quarantine_item(self, item):
        vault_path = os.path.join(self.vault_dir, item["id"])
        try:
            if os.path.exists(vault_path):
                os.remove(vault_path)
            q_data = [x for x in self.load_json(self.quarantine_db_file) if x["id"] != item["id"]]
            self.save_json(self.quarantine_db_file, q_data)
            self.refresh_quarantine_list()
        except Exception as e:
            messagebox.showerror("Erro ao excluir", str(e))

    # ==========================================================
    # TELA 5: HISTÓRICO
    # ==========================================================
    def create_history_screen(self):
        frame = ctk.CTkFrame(self.main_area, fg_color="transparent")

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(header, text="Histórico de Verificações", font=("Segoe UI", 24, "bold"), text_color="#FFFFFF").pack(side="left")
        ctk.CTkButton(
            header, text="Limpar Histórico", width=130, height=32, fg_color="#131B2E", hover_color="#1E293B",
            command=self.clear_history
        ).pack(side="right")

        self.history_scroll = ctk.CTkScrollableFrame(frame, fg_color="#0E1525", border_color="#1A263D", border_width=1, corner_radius=10)
        self.history_scroll.pack(fill="both", expand=True)

        self.screens["history"] = frame

    def refresh_history_list(self):
        for widget in self.history_scroll.winfo_children():
            widget.destroy()

        history = self.load_json(self.history_db_file)
        if not history:
            ctk.CTkLabel(self.history_scroll, text="📜 Nenhuma verificação registrada ainda.", font=("Segoe UI", 13), text_color="#6C7E96").pack(pady=40)
            return

        for entry in history:
            card = ctk.CTkFrame(self.history_scroll, fg_color="#131B2E", corner_radius=8)
            card.pack(fill="x", padx=10, pady=5)

            status_color = "#FF4C4C" if entry["threats"] > 0 else "#00FF88"
            status_text = f"⚠️ {entry['threats']} ameaça(s)" if entry["threats"] > 0 else "✅ Limpo"

            ctk.CTkLabel(card, text=f"{entry['date']}  |  {status_text}", font=("Segoe UI", 13, "bold"), text_color=status_color).pack(anchor="w", padx=15, pady=(8, 2))
            ctk.CTkLabel(card, text=f"Alvo: {entry['target']}  •  Arquivos analisados: {entry['scanned']}", font=("Segoe UI", 11), text_color="#A0B2C6").pack(anchor="w", padx=15, pady=(0, 8))

    def clear_history(self):
        self.save_json(self.history_db_file, [])
        self.refresh_history_list()

    # ==========================================================
    # TELA 6: PLANOS & ASSINATURA (PAGBANK AUTOMÁTICO SEM CHAVE)
    # ==========================================================
    def create_plans_screen(self):
        frame = ctk.CTkFrame(self.main_area, fg_color="transparent")

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x")
        ctk.CTkLabel(
            header,
            text="Planos & Assinatura",
            font=("Segoe UI", 24, "bold"),
            text_color="#FFFFFF"
        ).pack(side="left")
        self.btn_account = ctk.CTkButton(
            header,
            text="Entrar / Criar conta",
            width=190,
            height=34,
            command=self.open_account_modal
        )
        self.btn_account.pack(side="right")

        self.lbl_plans_status = ctk.CTkLabel(
            frame,
            text="Verificando status da licença...",
            font=("Segoe UI", 13, "bold"),
            text_color="#00FF88"
        )
        self.lbl_plans_status.pack(anchor="w", pady=(4, 16))

        # Grade com os 3 Planos
        plans_grid = ctk.CTkFrame(frame, fg_color="transparent")
        plans_grid.pack(fill="x", pady=(0, 16))
        plans_grid.grid_columnconfigure((0, 1, 2), weight=1)

        plans_info = [
            {
                "key": "weekly",
                "title": "Plano Semanal",
                "price_cents": 700,
                "price_str": "R$ 7,00",
                "period": "por semana (7 dias)",
                "days": 7,
                "desc": "• Escudo em Tempo Real\n• Scanner SHA-256\n• Liberação Imediata PagBank",
                "highlight": False,
                "badge": "FLEXÍVEL"
            },
            {
                "key": "monthly",
                "title": "Plano Mensal",
                "price_cents": 1400,
                "price_str": "R$ 14,00",
                "period": "por mês (30 dias)",
                "days": 30,
                "desc": "• Proteção Completa 24h\n• Análise Heurística\n• Suporte Campos Tecnologia",
                "highlight": False,
                "badge": "POPULAR"
            },
            {
                "key": "annual",
                "title": "Plano Anual",
                "price_cents": 5000,
                "price_str": "R$ 50,00",
                "period": "por ano (365 dias)",
                "days": 365,
                "desc": "• Economia Máxima (R$ 4,16/mês)\n• Todas as Atualizações\n• Prioridade no Suporte",
                "highlight": True,
                "badge": "MAIS VANTAJOSO"
            }
        ]

        for idx, p in enumerate(plans_info):
            border_col = "#00E5FF" if p["highlight"] else "#1A263D"
            card = ctk.CTkFrame(plans_grid, fg_color="#0E1525", border_color=border_col, border_width=2 if p["highlight"] else 1, corner_radius=12)
            card.grid(row=0, column=idx, padx=8, sticky="nsew")

            ctk.CTkLabel(
                card,
                text=p["badge"],
                font=("Segoe UI", 10, "bold"),
                text_color="#050811" if p["highlight"] else "#00E5FF",
                fg_color="#00E5FF" if p["highlight"] else "#131B2E",
                corner_radius=5,
                height=22
            ).pack(pady=(14, 8), padx=16, fill="x")

            ctk.CTkLabel(card, text=p["title"].upper(), font=("Segoe UI", 14, "bold"), text_color="#FFFFFF").pack()
            ctk.CTkLabel(card, text=p["price_str"], font=("Segoe UI", 26, "bold"), text_color="#00E5FF").pack(pady=(4, 0))
            ctk.CTkLabel(card, text=p["period"], font=("Segoe UI", 11), text_color="#A0B2C6").pack(pady=(0, 12))

            ctk.CTkLabel(card, text=p["desc"], font=("Segoe UI", 12), text_color="#CBD5E1", justify="left").pack(pady=(0, 16), padx=14)

            ctk.CTkButton(
                card,
                text="Pagar e Ativar Agora",
                font=("Segoe UI", 13, "bold"),
                fg_color="#00E5FF" if p["highlight"] else "#131B2E",
                text_color="#050811" if p["highlight"] else "#00E5FF",
                border_color="#00E5FF",
                border_width=1,
                hover_color="#33ECFF" if p["highlight"] else "#1E293B",
                height=40,
                corner_radius=8,
                command=lambda plan=p: self.open_account_payment_modal(plan)
            ).pack(pady=(0, 16), padx=16, fill="x")

        # Informativo PagBank
        info_box = ctk.CTkFrame(frame, fg_color="#0E1525", border_color="#1A263D", border_width=1, corner_radius=12)
        info_box.pack(fill="x")

        ctk.CTkLabel(
            info_box,
            text="⚡ Pagamento PagBank vinculado à sua conta",
            font=("Segoe UI", 14, "bold"),
            text_color="#00FF88"
        ).pack(anchor="w", padx=20, pady=(14, 4))

        ctk.CTkLabel(
            info_box,
            text="Pague com PIX, cartão de crédito ou débito. O plano será vinculado à sua conta e poderá ser recuperado após reinstalar o aplicativo.",
            font=("Segoe UI", 12),
            text_color="#A0B2C6",
            justify="left"
        ).pack(anchor="w", padx=20, pady=(0, 14))

        self.screens["plans"] = frame

    def open_account_payment_modal(self, plan):
        if not self.account_session:
            messagebox.showwarning(
                "Entre na sua conta",
                "Entre ou crie uma conta antes de iniciar um pagamento. O plano será vinculado a essa conta."
            )
            self.open_account_modal()
            return

        modal = ctk.CTkToplevel(self)
        modal.title(f"Pagamento PagBank — {plan['title']}")
        modal.geometry("500x500")
        modal.resizable(False, False)
        modal.configure(fg_color="#090C15")
        modal.transient(self)
        modal.grab_set()

        def on_close_modal():
            self.checking_payment = False
            modal.destroy()

        modal.protocol("WM_DELETE_WINDOW", on_close_modal)

        ctk.CTkLabel(
            modal,
            text=f"{plan['title']} — {plan['price_str']}",
            font=("Segoe UI", 20, "bold"),
            text_color="#00E5FF"
        ).pack(pady=(18, 4))
        ctk.CTkLabel(
            modal,
            text=f"Conta: {self.account_email}",
            font=("Segoe UI", 12),
            text_color="#A0B2C6"
        ).pack(pady=(0, 12))

        entry_name = ctk.CTkEntry(
            modal,
            placeholder_text="Nome e Sobrenome",
            font=("Segoe UI", 13),
            height=36,
            width=400,
            fg_color="#0E1525",
            border_color="#1A263D"
        )
        entry_name.pack(pady=4)
        entry_cpf = ctk.CTkEntry(
            modal,
            placeholder_text="CPF (11 números - exigido pelo PagBank)",
            font=("Segoe UI", 13),
            height=36,
            width=400,
            fg_color="#0E1525",
            border_color="#1A263D"
        )
        entry_cpf.pack(pady=(4, 12))

        status_label = ctk.CTkLabel(
            modal,
            text="",
            font=("Segoe UI", 12, "bold"),
            text_color="#00FF88",
            wraplength=430
        )
        pix_box = ctk.CTkTextbox(
            modal,
            height=75,
            width=400,
            fg_color="#0E1525",
            text_color="#00E5FF",
            font=("Consolas", 11)
        )

        def start_payment(method):
            name = entry_name.get().strip()
            cpf = "".join(filter(str.isdigit, entry_cpf.get()))
            if len(name.split()) < 2:
                messagebox.showwarning("Nome inválido", "Informe seu nome e sobrenome.")
                return
            if len(cpf) != 11:
                messagebox.showwarning("CPF obrigatório", "Informe um CPF com 11 números.")
                return

            status_label.pack(pady=(8, 4))
            status_label.configure(text="Gerando pagamento seguro...", text_color="#00E5FF")
            self.checking_payment = True
            threading.Thread(
                target=self.process_account_payment,
                args=(modal, plan, method, name, cpf, status_label, pix_box),
                daemon=True
            ).start()

        for label, method in (
            ("💠  Pagar com PIX", "PIX"),
            ("💳  Cartão de Crédito", "Cartão de Crédito"),
            ("🏧  Cartão de Débito", "Cartão de Débito")
        ):
            ctk.CTkButton(
                modal,
                text=label,
                font=("Segoe UI", 13, "bold"),
                fg_color="#00E5FF" if method == "PIX" else "#131B2E",
                text_color="#050811" if method == "PIX" else "#FFFFFF",
                border_color="#00E5FF",
                border_width=1,
                hover_color="#33ECFF" if method == "PIX" else "#1E293B",
                height=40,
                width=400,
                corner_radius=8,
                command=lambda selected_method=method: start_payment(selected_method)
            ).pack(pady=5)

    def process_account_payment(self, modal, plan, method, name, cpf, status_label, pix_box):
        session = self.account_session
        if not session:
            self.after(0, lambda: self.set_account_status(
                status_label, "Entre novamente na sua conta para continuar.", "#FF4C4C"
            ))
            return

        try:
            payment = self.cloud_client.create_payment(session, plan["key"], method, name, cpf)
            payment_id = payment.get("payment_id")
            if not payment_id:
                raise CloudAccountError("O servidor não retornou o identificador do pagamento.")

            pix_text = payment.get("pix_text")
            checkout_url = payment.get("checkout_url")
            if pix_text:
                def show_pix():
                    if modal.winfo_exists():
                        self.set_account_status(
                            status_label,
                            "Código PIX gerado. Pague no aplicativo do seu banco; estamos confirmando.",
                            "#00FF88"
                        )
                        pix_box.pack(pady=6)
                        pix_box.insert("1.0", pix_text)
                self.after(0, show_pix)
            elif checkout_url:
                webbrowser.open(checkout_url)
                self.after(0, lambda: self.set_account_status(
                    status_label,
                    "Checkout PagBank aberto no navegador. Conclua o pagamento para ativar o plano.",
                    "#00E5FF"
                ))
            else:
                raise CloudAccountError("O servidor não retornou os dados do pagamento.")
        except CloudAccountError as exc:
            error = str(exc)
            self.after(0, lambda: self.set_account_status(status_label, error, "#FF4C4C"))
            self.checking_payment = False
            return

        while self.checking_payment:
            try:
                result = self.cloud_client.sync_plan(session, payment_id)
            except CloudAccountError as exc:
                error = str(exc)
                self.after(0, lambda: self.set_account_status(status_label, error, "#FF4C4C"))
                self.checking_payment = False
                return

            if result.get("payment_status") == "paid" and result.get("plan"):
                plan_data = result["plan"]
                self.after(
                    0,
                    lambda: self.finish_account_payment(
                        modal, plan_data, plan["title"], method, payment_id, session["user_id"]
                    )
                )
                return
            if result.get("payment_status") == "not_found":
                self.after(0, lambda: self.set_account_status(
                    status_label, "Pagamento não encontrado para esta conta.", "#FF4C4C"
                ))
                self.checking_payment = False
                return
            time.sleep(5)

    def finish_account_payment(self, modal, plan_data, plan_title, method, payment_id, user_id):
        self.checking_payment = False
        if modal.winfo_exists():
            modal.destroy()
        if self.account_user_id != user_id:
            return
        self.apply_cloud_plan(plan_data, user_id)
        messagebox.showinfo(
            "Pagamento confirmado",
            f"Pagamento via {method} confirmado pelo PagBank.\n\n"
            f"Plano: {plan_title}\n"
            f"Conta: {self.account_email}\n"
            f"Identificador: {payment_id}"
        )

    # ==========================================================
    # TELA 7: CONFIGURAÇÕES & ATUALIZAÇÕES
    # ==========================================================
    def create_settings_screen(self):
        frame = ctk.CTkFrame(self.main_area, fg_color="transparent")

        ctk.CTkLabel(frame, text="Configurações do Sistema", font=("Segoe UI", 24, "bold"), text_color="#FFFFFF").pack(anchor="w")
        ctk.CTkLabel(frame, text="Gerencie o comportamento do motor de proteção, inicialização e atualizações.", font=("Segoe UI", 13), text_color="#A0B2C6").pack(anchor="w", pady=(2, 16))

        opts_card = ctk.CTkFrame(frame, fg_color="#0E1525", border_color="#1A263D", border_width=1, corner_radius=12)
        opts_card.pack(fill="x", pady=(0, 14))

        self.sw_startup = ctk.CTkSwitch(
            opts_card,
            text="Iniciar automaticamente junto com o Windows (proteção ativa ao ligar o PC)",
            font=("Segoe UI", 13, "bold"),
            text_color="#00E5FF",
            progress_color="#00E5FF",
            command=self.toggle_windows_startup
        )
        if self.settings.get("start_with_windows", False):
            self.sw_startup.select()
        self.sw_startup.pack(anchor="w", padx=20, pady=(16, 12))

        self.sw_auto_quarantine = ctk.CTkSwitch(
            opts_card,
            text="Quarentena Automática (isolar ameaças imediatamente sem perguntar)",
            font=("Segoe UI", 13, "bold"),
            text_color="#FFFFFF",
            progress_color="#00E5FF",
            command=self.update_settings_switches
        )
        if self.settings.get("auto_quarantine", True):
            self.sw_auto_quarantine.select()
        self.sw_auto_quarantine.pack(anchor="w", padx=20, pady=(0, 12))

        self.sw_heuristic = ctk.CTkSwitch(
            opts_card,
            text="Análise Heurística (detectar arquivos disfarçados com extensão dupla)",
            font=("Segoe UI", 13, "bold"),
            text_color="#FFFFFF",
            progress_color="#00E5FF",
            command=self.update_settings_switches
        )
        if self.settings.get("heuristic_scan", True):
            self.sw_heuristic.select()
        self.sw_heuristic.pack(anchor="w", padx=20, pady=(0, 16))

        update_card = ctk.CTkFrame(frame, fg_color="#0E1525", border_color="#1A263D", border_width=1, corner_radius=12)
        update_card.pack(fill="x", pady=(0, 14))

        upd_row = ctk.CTkFrame(update_card, fg_color="transparent")
        upd_row.pack(fill="x", padx=20, pady=16)

        upd_info = ctk.CTkFrame(upd_row, fg_color="transparent")
        upd_info.pack(side="left")

        self.lbl_settings_db = ctk.CTkLabel(
            upd_info,
            text=f"Banco de Assinaturas: {self.db_version}",
            font=("Segoe UI", 14, "bold"),
            text_color="#00FF88"
        )
        self.lbl_settings_db.pack(anchor="w")

        ctk.CTkLabel(
            upd_info,
            text="Assinaturas SHA-256 e regras heurísticas oficiais Campos Defenser.",
            font=("Segoe UI", 12),
            text_color="#A0B2C6"
        ).pack(anchor="w")

        ctk.CTkButton(
            upd_row,
            text="🔄  Verificar Atualizações",
            font=("Segoe UI", 13, "bold"),
            fg_color="#00E5FF",
            text_color="#050811",
            hover_color="#33ECFF",
            height=40,
            width=195,
            corner_radius=8,
            command=self.check_database_updates
        ).pack(side="right")

        about_card = ctk.CTkFrame(frame, fg_color="#0E1525", border_color="#1A263D", border_width=1, corner_radius=12)
        about_card.pack(fill="x")

        ctk.CTkLabel(
            about_card,
            text="CAMPOS DEFENSER — Edição Windows 10 / 11",
            font=("Segoe UI", 14, "bold"),
            text_color="#00E5FF"
        ).pack(anchor="w", padx=20, pady=(14, 4))

        ctk.CTkLabel(
            about_card,
            text="Desenvolvido por Campos Tecnologia • Sua segurança digital sempre protegida.",
            font=("Segoe UI", 12),
            text_color="#A0B2C6"
        ).pack(anchor="w", padx=20, pady=(0, 14))

        self.screens["settings"] = frame

    def toggle_windows_startup(self):
        desired_state = bool(self.sw_startup.get())
        success = self.set_windows_startup(desired_state)
        if success:
            self.settings["start_with_windows"] = desired_state
            self.save_settings()
        else:
            if desired_state:
                self.sw_startup.deselect()
            else:
                self.sw_startup.select()

    def update_settings_switches(self):
        self.settings["auto_quarantine"] = bool(self.sw_auto_quarantine.get())
        self.settings["heuristic_scan"] = bool(self.sw_heuristic.get())
        self.save_settings()

    def check_database_updates(self):
        today_ver = datetime.now().strftime("v%Y.%m.%d")
        self.db_version = today_ver
        self.settings["db_version"] = today_ver
        self.save_settings()

        self.lbl_settings_db.configure(text=f"Banco de Assinaturas: {self.db_version} (Atualizado)")
        self.dash_db_label.configure(text=f"Atualizado ({self.db_version})")
        messagebox.showinfo(
            "Campos Defenser — Atualização",
            f"O banco de assinaturas da Campos Tecnologia está atualizado!\n\nVersão ativa: {self.db_version}"
        )

    # ==========================================================
    # NAVEGAÇÃO ENTRE TELAS (COM BLOQUEIO SE EXPIRADO)
    # ==========================================================
    def show_screen(self, screen_key):
        if not self.is_license_valid() and screen_key not in ("plans", "settings"):
            messagebox.showwarning(
                "Campos Defenser — Período Grátis Encerrado",
                "Seu período de 1 dia grátis expirou!\n\nEscolha um plano (Semanal R$ 7,00 | Mensal R$ 14,00 | Anual R$ 50,00) e pague via PagBank (PIX, Crédito ou Débito) para liberar automaticamente."
            )
            screen_key = "plans"

        for frame in self.screens.values():
            frame.grid_forget()

        for key, btn in self.menu_buttons.items():
            if key == screen_key:
                btn.configure(fg_color="#131B2E", text_color="#00E5FF")
            else:
                btn.configure(fg_color="transparent", text_color="#A0B2C6")

        if screen_key == "quarantine":
            self.refresh_quarantine_list()
        elif screen_key == "history":
            self.refresh_history_list()
        elif screen_key == "plans":
            self.update_license_ui()

        self.screens[screen_key].grid(row=0, column=0, sticky="nsew")


if __name__ == "__main__":
    app = CamposDefenserApp()
    app.mainloop()