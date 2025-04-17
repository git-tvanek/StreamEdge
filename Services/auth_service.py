#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AuthService - Služba pro správu autentizace k MagentaTV/MagioTV API
"""
import os
import json
import time
import uuid
import logging
import requests

from Services.base.service_base import ServiceBase
from Services.utils.constants import API_ENDPOINTS, TIME_CONSTANTS

logger = logging.getLogger(__name__)


class AuthService(ServiceBase):
    """
    Služba pro správu autentizace a tokenů
    """

    def __init__(self, username, password, language="cz", device_id=None, device_name="Android TV",
                 device_type="OTT_STB"):
        """
        Inicializace služby pro autentizaci

        Args:
            username (str): Přihlašovací jméno
            password (str): Heslo
            language (str): Kód jazyka (cz, sk)
            device_id (str, optional): ID zařízení nebo None pro vygenerování nového
            device_name (str): Název zařízení
            device_type (str): Typ zařízení
        """
        super().__init__("auth")
        self.username = username
        self.password = password
        self.language = language.lower()

        # URL podle jazyka
        self.base_url = f"https://{self.language}go.magio.tv"

        # User-Agent
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 MagioGO/4.0.21"

        # Session pro HTTP požadavky
        self.session = requests.Session()

        # Informace o zařízení
        self.device_id = device_id or str(uuid.uuid4())
        self.device_name = device_name
        self.device_type = device_type

        # Tokeny
        self.access_token = None
        self.refresh_token = None
        self.token_expires = 0

        # Soubor pro uložení přihlašovacích údajů
        data_dir = self._get_config("DATA_DIR", "data")
        self.token_file = os.path.join(data_dir, f"token_{language}.json")

        # Načtení tokenů při inicializaci
        self._load_tokens()

        # Vytvoření HTTP klienta
        self._http_client = self._create_http_client(
            base_url=self.base_url,
            language=self.language,
            user_agent=self.user_agent
        )

    def _load_tokens(self):
        """Načtení tokenů ze souboru"""
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, 'r') as f:
                    data = json.load(f)
                    self.access_token = data.get("access_token")
                    self.refresh_token = data.get("refresh_token")
                    self.token_expires = data.get("expires", 0)
                    self.device_id = data.get("device_id", self.device_id)
                self.logger.info("Tokeny načteny ze souboru")
            except Exception as e:
                self.logger.error(f"Chyba při načítání tokenů: {e}")

    def _save_tokens(self):
        """Uložení tokenů do souboru"""
        try:
            # Vytvoření adresáře, pokud neexistuje
            os.makedirs(os.path.dirname(self.token_file), exist_ok=True)

            with open(self.token_file, 'w') as f:
                json.dump({
                    "access_token": self.access_token,
                    "refresh_token": self.refresh_token,
                    "expires": self.token_expires,
                    "device_id": self.device_id
                }, f)
            self.logger.info("Tokeny uloženy do souboru")
        except Exception as e:
            self.logger.error(f"Chyba při ukládání tokenů: {e}")

    def login(self):
        """
        Přihlášení k službě MagentaTV

        Returns:
            bool: True v případě úspěšného přihlášení, jinak False
        """
        # Ověření platnosti současného tokenu
        if self.refresh_token and self.token_expires > time.time() + TIME_CONSTANTS["TOKEN_REFRESH_BEFORE_EXPIRY"]:
            self.logger.info("Současný token je stále platný")
            return self.refresh_access_token()

        app_version = self._get_config("APP_VERSION", "4.0.25-hf.0")

        # Parametry pro inicializaci přihlášení
        params = {
            "dsid": self.device_id,
            "deviceName": self.device_name,
            "deviceType": self.device_type,
            "osVersion": "0.0.0",
            "appVersion": app_version,
            "language": self.language.upper(),
            "devicePlatform": "GO"
        }

        headers = {
            "Host": f"{self.language}go.magio.tv",
            "User-Agent": self.user_agent
        }

        try:
            # První požadavek na inicializaci přihlášení
            init_response = self.session.post(
                f"{self.base_url}{API_ENDPOINTS['auth']['init']}",
                params=params,
                headers=headers,
                timeout=TIME_CONSTANTS["DEFAULT_TIMEOUT"]
            ).json()

            if not init_response.get("success", False):
                error_msg = init_response.get('errorMessage', 'Neznámá chyba')
                self.logger.error(f"Chyba inicializace: {error_msg}")
                return False

            # Získání dočasného přístupového tokenu
            temp_access_token = init_response["token"]["accessToken"]

            # Parametry pro přihlášení s uživatelským jménem a heslem
            login_params = {
                "loginOrNickname": self.username,
                "password": self.password
            }

            login_headers = {
                "Content-type": "application/json",
                "Authorization": f"Bearer {temp_access_token}",
                "Host": f"{self.language}go.magio.tv",
                "User-Agent": self.user_agent
            }

            # Požadavek na přihlášení
            login_response = self.session.post(
                f"{self.base_url}{API_ENDPOINTS['auth']['login']}",
                json=login_params,
                headers=login_headers,
                timeout=TIME_CONSTANTS["DEFAULT_TIMEOUT"]
            ).json()

            if not login_response.get("success", False):
                error_msg = login_response.get('errorMessage', 'Neznámá chyba')
                self.logger.error(f"Chyba přihlášení: {error_msg}")
                return False

            # Uložení přihlašovacích tokenů
            self.access_token = login_response["token"]["accessToken"]
            self.refresh_token = login_response["token"]["refreshToken"]
            self.token_expires = time.time() + login_response["token"]["expiresIn"] / 1000

            # Uložení tokenů do souboru
            self._save_tokens()

            self.logger.info("Přihlášení úspěšné")
            return True

        except Exception as e:
            self.logger.error(f"Chyba při přihlášení: {e}")
            return False

    def refresh_access_token(self):
        """
        Obnovení přístupového tokenu pomocí refresh tokenu

        Returns:
            bool: True v případě úspěšného obnovení tokenu, jinak False
        """
        if not self.refresh_token:
            self.logger.warning("Refresh token není k dispozici, je nutné se znovu přihlásit")
            return self.login()

        # Kontrola vypršení tokenu
        if self.token_expires > time.time() + TIME_CONSTANTS["TOKEN_REFRESH_BEFORE_EXPIRY"]:
            return True

        params = {
            "refreshToken": self.refresh_token
        }

        headers = {
            "Content-type": "application/json",
            "Host": f"{self.language}go.magio.tv",
            "User-Agent": self.user_agent
        }

        try:
            response = self.session.post(
                f"{self.base_url}{API_ENDPOINTS['auth']['tokens']}",
                json=params,
                headers=headers,
                timeout=TIME_CONSTANTS["DEFAULT_TIMEOUT"]
            ).json()

            if not response.get("success", False):
                error_msg = response.get('errorMessage', 'Neznámá chyba')
                self.logger.error(f"Chyba obnovení tokenu: {error_msg}")
                return self.login()

            self.access_token = response["token"]["accessToken"]
            self.refresh_token = response["token"]["refreshToken"]
            self.token_expires = time.time() + response["token"]["expiresIn"] / 1000

            # Uložení tokenů do souboru
            self._save_tokens()

            self.logger.info("Token úspěšně obnoven")
            return True

        except Exception as e:
            self.logger.error(f"Chyba při obnovení tokenu: {e}")
            return self.login()

    def get_auth_headers(self):
        """
        Získání autorizačních hlaviček pro API požadavky

        Returns:
            dict: Hlavičky s autorizačním tokenem nebo None při chybě
        """
        if not self.refresh_access_token():
            return None

        return {
            "Authorization": f"Bearer {self.access_token}",
            "Host": f"{self.language}go.magio.tv",
            "User-Agent": self.user_agent
        }

    def get_base_url(self):
        """
        Získání základní URL pro API požadavky

        Returns:
            str: Základní URL
        """
        return self.base_url

    def logout(self):
        """
        Odhlášení a vymazání tokenů

        Returns:
            bool: True pokud bylo odhlášení úspěšné
        """
        self.access_token = None
        self.refresh_token = None
        self.token_expires = 0

        # Smazání souboru s tokeny
        if os.path.exists(self.token_file):
            try:
                os.remove(self.token_file)
                return True
            except Exception as e:
                self.logger.error(f"Chyba při mazání souboru s tokeny: {e}")
                return False

        return True