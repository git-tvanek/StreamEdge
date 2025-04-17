#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AuthService - Služba pro správu autentizace k MagentaTV/MagioTV API

Tato služba zajišťuje autentizaci uživatele a správu tokenů.
Využívá SessionService pro HTTP komunikaci, ConfigService pro konfiguraci,
CacheService pro cachování tokenů a SystemService pro monitorování.
"""
import os
import json
import time
import uuid
import logging
import requests
from urllib.parse import urlparse

from Services.base.service_base import ServiceBase
from Services.utils.constants import API_ENDPOINTS, TIME_CONSTANTS, BASE_URLS, DEFAULT_USER_AGENT

logger = logging.getLogger(__name__)


class AuthService(ServiceBase):
    """
    Služba pro správu autentizace a tokenů

    Zajišťuje přihlašování, správu a obnovu přístupových tokenů pro API
    """

    def __init__(self,
                 username=None,
                 password=None,
                 session_service=None,
                 config_service=None,
                 cache_service=None,
                 system_service=None,
                 device_id=None,
                 device_name=None,
                 device_type=None):
        """
        Inicializace služby pro autentizaci

        Args:
            username (str, optional): Přihlašovací jméno nebo None pro načtení z konfigurace
            password (str, optional): Heslo nebo None pro načtení z konfigurace
            session_service (SessionService, optional): Služba pro HTTP komunikaci
            config_service (ConfigService, optional): Služba pro přístup ke konfiguraci
            cache_service (CacheService, optional): Služba pro cachování dat
            system_service (SystemService, optional): Služba pro systémové operace
            device_id (str, optional): ID zařízení nebo None pro načtení/generování
            device_name (str, optional): Název zařízení nebo None pro načtení z konfigurace
            device_type (str, optional): Typ zařízení nebo None pro načtení z konfigurace
        """
        super().__init__("auth")

        # Uložení závislostí
        self.session_service = session_service
        self.config_service = config_service
        self.cache_service = cache_service
        self.system_service = system_service

        # Načtení konfigurace
        self._load_config(username, password, device_name, device_type)

        # Informace o zařízení
        self.device_id = device_id or self._get_device_id()

        # Tokeny
        self.access_token = None
        self.refresh_token = None
        self.token_expires = 0

        # Soubor pro uložení přihlašovacích údajů
        data_dir = self._get_data_dir()
        self.token_file = os.path.join(data_dir, f"token_{self.language}.json")

        # Vytvoření HTTP klienta, pokud není zadán
        if self.session_service is None:
            self.session = requests.Session()
        else:
            self.session = self.session_service.session

        # Načtení tokenů při inicializaci
        self._load_tokens()

        # Registrace u SystemService, pokud je k dispozici
        if self.system_service:
            self.system_service.register_auth_service(self)

        self.logger.info(f"AuthService inicializována (jazyk: {self.language})")

    def _load_config(self, username, password, device_name, device_type):
        """
        Načtení konfigurace z ConfigService nebo z parametrů

        Args:
            username (str): Přihlašovací jméno nebo None
            password (str): Heslo nebo None
            device_name (str): Název zařízení nebo None
            device_type (str): Typ zařízení nebo None
        """
        # Pokud máme ConfigService, použijeme ji pro načtení konfigurace
        if self.config_service:
            self.username = username or self.config_service.get_value("USERNAME", "")
            self.password = password or self.config_service.get_value("PASSWORD", "")
            self.language = self.config_service.get_value("LANGUAGE", "cz").lower()
            self.device_name = device_name or self.config_service.get_value("DEVICE_NAME", "Android TV")
            self.device_type = device_type or self.config_service.get_value("DEVICE_TYPE", "OTT_STB")
            self.user_agent = self.config_service.get_value("USER_AGENT", DEFAULT_USER_AGENT)
            self.app_version = self.config_service.get_value("APP_VERSION", "4.0.25-hf.0")
        else:
            # Pokud nemáme ConfigService, použijeme parametry nebo výchozí hodnoty
            self.username = username or ""
            self.password = password or ""
            self.language = "cz"
            self.device_name = device_name or "Android TV"
            self.device_type = device_type or "OTT_STB"
            self.user_agent = DEFAULT_USER_AGENT
            self.app_version = "4.0.25-hf.0"

        # URL podle jazyka
        self.base_url = BASE_URLS.get(self.language, f"https://{self.language}go.magio.tv")

    def _get_device_id(self):
        """
        Získání nebo generování ID zařízení

        Returns:
            str: ID zařízení
        """
        # Pokud máme ConfigService, pokusíme se načíst ID zařízení
        if self.config_service:
            device_id = self.config_service.get_value(f"DEVICE_ID_{self.language.upper()}", None)
            if device_id:
                return device_id

        # Pokud máme CacheService, pokusíme se načíst ID zařízení z cache
        if self.cache_service:
            device_id = self.cache_service.get_from_cache(f"device_id_{self.language}", lambda: None)
            if device_id:
                return device_id

        # Generování nového ID zařízení
        return str(uuid.uuid4())

    def _get_data_dir(self):
        """
        Získání adresáře pro data

        Returns:
            str: Cesta k adresáři pro data
        """
        if self.config_service:
            data_dir = self.config_service.get_value("DATA_DIR", "data")
        else:
            data_dir = "data"

        # Vytvoření adresáře, pokud neexistuje
        os.makedirs(data_dir, exist_ok=True)
        return data_dir

    def _save_device_id(self):
        """
        Uložení ID zařízení do konfigurace a cache
        """
        # Uložení do konfigurace
        if self.config_service:
            self.config_service.set_value(f"DEVICE_ID_{self.language.upper()}", self.device_id)

        # Uložení do cache
        if self.cache_service:
            # Uložení s dlouhou platností (týden)
            self.cache_service.store_in_cache(
                f"device_id_{self.language}",
                self.device_id,
                cache_timeout=7 * 24 * 3600
            )

    def _load_tokens(self):
        """
        Načtení tokenů z cache nebo ze souboru
        """
        tokens_loaded = False

        # Pokus o načtení z cache
        if self.cache_service:
            try:
                token_data = self.cache_service.get_from_cache(f"auth_tokens_{self.language}", lambda: None)
                if token_data:
                    self.access_token = token_data.get("access_token")
                    self.refresh_token = token_data.get("refresh_token")
                    self.token_expires = token_data.get("expires", 0)
                    self.device_id = token_data.get("device_id", self.device_id)
                    tokens_loaded = True
                    self.logger.info("Tokeny načteny z cache")
            except Exception as e:
                self.logger.warning(f"Chyba při načítání tokenů z cache: {e}")

        # Pokud se nepodařilo načíst z cache, zkusíme soubor
        if not tokens_loaded and os.path.exists(self.token_file):
            try:
                with open(self.token_file, 'r') as f:
                    data = json.load(f)
                    self.access_token = data.get("access_token")
                    self.refresh_token = data.get("refresh_token")
                    self.token_expires = data.get("expires", 0)
                    self.device_id = data.get("device_id", self.device_id)
                self.logger.info("Tokeny načteny ze souboru")

                # Uložíme tokeny do cache, pokud je k dispozici
                if self.cache_service:
                    self._store_tokens_in_cache()
            except Exception as e:
                self.logger.error(f"Chyba při načítání tokenů ze souboru: {e}")

    def _store_tokens_in_cache(self):
        """
        Uložení tokenů do cache
        """
        if not self.cache_service:
            return

        try:
            token_data = {
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
                "expires": self.token_expires,
                "device_id": self.device_id
            }

            # Výpočet zbývající platnosti tokenů (max. 7 dní)
            time_left = max(0, int(self.token_expires - time.time()))
            ttl = min(time_left, 7 * 24 * 3600)  # max 7 dní

            # Uložení do cache jen pokud mají tokeny ještě nějakou platnost
            if ttl > 0:
                self.cache_service.store_in_cache(
                    f"auth_tokens_{self.language}",
                    token_data,
                    cache_timeout=ttl
                )
        except Exception as e:
            self.logger.warning(f"Chyba při ukládání tokenů do cache: {e}")

    def _save_tokens(self):
        """
        Uložení tokenů do souboru a cache
        """
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

            # Uložení do cache
            self._store_tokens_in_cache()

            # Uložení ID zařízení
            self._save_device_id()

            # Aktualizace stavu v SystemService, pokud je k dispozici
            if self.system_service:
                self.system_service.update_auth_status()
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

        # Kontrola přihlašovacích údajů
        if not self.username or not self.password:
            self.logger.error("Přihlašovací údaje nejsou zadány")
            return False

        # Parametry pro inicializaci přihlášení
        params = {
            "dsid": self.device_id,
            "deviceName": self.device_name,
            "deviceType": self.device_type,
            "osVersion": "0.0.0",
            "appVersion": self.app_version,
            "language": self.language.upper(),
            "devicePlatform": "GO"
        }

        headers = {
            "Host": urlparse(self.base_url).netloc,
            "User-Agent": self.user_agent
        }

        try:
            # Použití SessionService pokud je k dispozici
            if self.session_service:
                init_response = self.session_service.post_json(
                    f"{self.base_url}{API_ENDPOINTS['auth']['init']}",
                    params=params,
                    headers=headers,
                    timeout=TIME_CONSTANTS["DEFAULT_TIMEOUT"]
                )
            else:
                # Jinak použijeme vlastní session
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
                "Host": urlparse(self.base_url).netloc,
                "User-Agent": self.user_agent
            }

            # Požadavek na přihlášení
            if self.session_service:
                login_response = self.session_service.post_json(
                    f"{self.base_url}{API_ENDPOINTS['auth']['login']}",
                    json=login_params,
                    headers=login_headers,
                    timeout=TIME_CONSTANTS["DEFAULT_TIMEOUT"]
                )
            else:
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

            # Uložení tokenů
            self._save_tokens()

            # Aktualizace stavu v SystemService, pokud je k dispozici
            if self.system_service:
                self.system_service.update_auth_status()

            self.logger.info("Přihlášení úspěšné")
            return True

        except Exception as e:
            self.logger.error(f"Chyba při přihlášení: {e}")

            # Zaznamenání chyby v SystemService, pokud je k dispozici
            if self.system_service:
                self.system_service.log_error("auth", f"Chyba při přihlášení: {e}")

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

        # Zkusit nejprve načíst z cache, pokud máme CacheService
        if self.cache_service:
            token_data = self.cache_service.get_from_cache(f"auth_tokens_{self.language}", lambda: None)
            if token_data and token_data.get("expires", 0) > time.time() + TIME_CONSTANTS[
                "TOKEN_REFRESH_BEFORE_EXPIRY"]:
                self.access_token = token_data.get("access_token")
                self.refresh_token = token_data.get("refresh_token")
                self.token_expires = token_data.get("expires", 0)
                self.logger.info("Tokeny načteny z cache během refresh operace")
                return True

        params = {
            "refreshToken": self.refresh_token
        }

        headers = {
            "Content-type": "application/json",
            "Host": urlparse(self.base_url).netloc,
            "User-Agent": self.user_agent
        }

        try:
            # Použití SessionService pokud je k dispozici
            if self.session_service:
                response = self.session_service.post_json(
                    f"{self.base_url}{API_ENDPOINTS['auth']['tokens']}",
                    json=params,
                    headers=headers,
                    timeout=TIME_CONSTANTS["DEFAULT_TIMEOUT"]
                )
            else:
                response = self.session.post(
                    f"{self.base_url}{API_ENDPOINTS['auth']['tokens']}",
                    json=params,
                    headers=headers,
                    timeout=TIME_CONSTANTS["DEFAULT_TIMEOUT"]
                ).json()

            if not response.get("success", False):
                error_msg = response.get('errorMessage', 'Neznámá chyba')
                self.logger.error(f"Chyba obnovení tokenu: {error_msg}")

                # Smazání tokenů z cache
                if self.cache_service:
                    self.cache_service.clear_cache(f"auth_tokens_{self.language}")

                return self.login()

            self.access_token = response["token"]["accessToken"]
            self.refresh_token = response["token"]["refreshToken"]
            self.token_expires = time.time() + response["token"]["expiresIn"] / 1000

            # Uložení tokenů
            self._save_tokens()

            self.logger.info("Token úspěšně obnoven")
            return True

        except Exception as e:
            self.logger.error(f"Chyba při obnovení tokenu: {e}")

            # Zaznamenání chyby v SystemService, pokud je k dispozici
            if self.system_service:
                self.system_service.log_error("auth", f"Chyba při obnovení tokenu: {e}")

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
            "Host": urlparse(self.base_url).netloc,
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

        # Smazání tokenů z cache
        if self.cache_service:
            self.cache_service.clear_cache(f"auth_tokens_{self.language}")

        # Smazání souboru s tokeny
        if os.path.exists(self.token_file):
            try:
                os.remove(self.token_file)
                self.logger.info("Soubor s tokeny byl smazán")
            except Exception as e:
                self.logger.error(f"Chyba při mazání souboru s tokeny: {e}")
                return False

        # Aktualizace stavu v SystemService, pokud je k dispozici
        if self.system_service:
            self.system_service.update_auth_status()

        self.logger.info("Uživatel byl úspěšně odhlášen")
        return True

    def get_auth_status(self):
        """
        Získání stavu autentizace

        Returns:
            dict: Stav autentizace
        """
        token_valid = self.access_token is not None and self.token_expires > time.time()
        refresh_valid = self.refresh_token is not None

        time_remaining = max(0, int(self.token_expires - time.time())) if token_valid else 0

        return {
            "authenticated": token_valid,
            "username": self.username if token_valid else None,
            "language": self.language,
            "device_id": self.device_id,
            "token_valid": token_valid,
            "refresh_valid": refresh_valid,
            "token_expires_in": time_remaining,
            "token_expires_formatted": self._format_time_remaining(time_remaining) if time_remaining > 0 else "vypršel"
        }

    def _format_time_remaining(self, seconds):
        """
        Formátování zbývajícího času do vypršení tokenu

        Args:
            seconds (int): Počet sekund

        Returns:
            str: Formátovaný čas
        """
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours > 0:
            return f"{int(hours)}h {int(minutes)}m"
        elif minutes > 0:
            return f"{int(minutes)}m {int(seconds)}s"
        else:
            return f"{int(seconds)}s"