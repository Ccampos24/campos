import json
import os
import sys
import time

import requests


class CloudAccountError(RuntimeError):
    pass


class CloudAccountClient:
    def __init__(self, config_path=None):
        if config_path is None:
            app_dir = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else __file__)
            candidates = [os.path.join(app_dir, "cloud_config.json")]
            bundled_dir = getattr(sys, "_MEIPASS", "")
            if bundled_dir:
                candidates.append(os.path.join(bundled_dir, "cloud_config.json"))
            config_path = next((path for path in candidates if os.path.isfile(path)), candidates[0])

        self.config_path = config_path
        self.config_error = None
        self.base_url = ""
        self.anon_key = ""

        try:
            with open(config_path, "r", encoding="utf-8") as config_file:
                config = json.load(config_file)
        except FileNotFoundError:
            self.config_error = f"Arquivo de configuração não encontrado: {config_path}"
            return
        except (OSError, json.JSONDecodeError) as exc:
            self.config_error = f"Não foi possível ler a configuração da conta online: {exc}"
            return

        if not isinstance(config, dict):
            self.config_error = "O arquivo cloud_config.json precisa conter um objeto JSON."
            return
        self.base_url = str(config.get("supabase_url", "")).strip().rstrip("/")
        self.anon_key = str(config.get("supabase_anon_key", "")).strip()
        if not self.base_url.startswith("https://") or not self.anon_key:
            self.config_error = "Configure a URL do projeto e a chave pública do Supabase em cloud_config.json."

    @property
    def is_configured(self):
        return self.config_error is None

    def _request(self, method, endpoint, payload=None, session=None):
        if not self.is_configured:
            raise CloudAccountError(self.config_error)

        headers = {
            "apikey": self.anon_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if session is not None:
            headers["Authorization"] = f"Bearer {self._access_token(session)}"

        try:
            response = requests.request(
                method,
                f"{self.base_url}{endpoint}",
                json=payload,
                headers=headers,
                timeout=20
            )
        except requests.RequestException as exc:
            raise CloudAccountError(f"Não foi possível conectar ao serviço de contas: {exc}") from exc

        try:
            data = response.json()
        except ValueError:
            data = {}
        if not isinstance(data, dict):
            data = {}

        if not response.ok:
            message = (
                data.get("msg")
                or data.get("message")
                or data.get("error_description")
                or data.get("error")
                or f"Resposta HTTP {response.status_code}"
            )
            raise CloudAccountError(str(message))

        return data

    @staticmethod
    def _make_session(data, fallback_email=""):
        access_token = data.get("access_token")
        if not access_token:
            return None
        user = data.get("user") or data
        return {
            "access_token": access_token,
            "refresh_token": data.get("refresh_token", ""),
            "expires_at": time.time() + int(data.get("expires_in", 3600)),
            "user_id": user.get("id", ""),
            "email": user.get("email", fallback_email)
        }

    def sign_up(self, email, password):
        data = self._request("POST", "/auth/v1/signup", {"email": email, "password": password})
        return self._make_session(data, email), data.get("user") or data

    def sign_in(self, email, password):
        data = self._request(
            "POST",
            "/auth/v1/token?grant_type=password",
            {"email": email, "password": password}
        )
        session = self._make_session(data, email)
        if session is None:
            raise CloudAccountError("O serviço não retornou uma sessão de acesso válida.")
        return session

    def reset_password(self, email):
        self._request("POST", "/auth/v1/recover", {"email": email})

    def _access_token(self, session):
        if session.get("expires_at", 0) > time.time() + 30:
            return session["access_token"]

        refresh_token = session.get("refresh_token")
        if not refresh_token:
            raise CloudAccountError("Sua sessão expirou. Entre na conta novamente.")

        data = self._request(
            "POST",
            "/auth/v1/token?grant_type=refresh_token",
            {"refresh_token": refresh_token}
        )
        refreshed = self._make_session(data, session.get("email", ""))
        if refreshed is None:
            raise CloudAccountError("Não foi possível renovar a sessão. Entre na conta novamente.")
        if not refreshed["user_id"]:
            refreshed["user_id"] = session.get("user_id", "")
        if not refreshed["email"]:
            refreshed["email"] = session.get("email", "")
        session.update(refreshed)
        return session["access_token"]

    def create_payment(self, session, plan_key, method, name, cpf):
        return self._request(
            "POST",
            "/functions/v1/create-pagbank-payment",
            {
                "plan_key": plan_key,
                "method": method,
                "name": name,
                "cpf": cpf
            },
            session=session
        )

    def sync_plan(self, session, payment_id=None):
        payload = {"payment_id": payment_id} if payment_id else {}
        return self._request(
            "POST",
            "/functions/v1/sync-plan",
            payload,
            session=session
        )
