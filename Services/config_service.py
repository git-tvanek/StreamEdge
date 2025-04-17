#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ConfigService - Služba pro správu konfigurace aplikace
"""
import os
import json
import logging
from Services.base.service_base import ServiceBase

logger = logging.getLogger(__name__)


class ConfigService(ServiceBase):
    """
    Služba pro správu konfigurace aplikace
    """

    def __init__(self, config_file=None):
        """
        Inicializace služby pro správu konfigurace

        Args:
            config_file (str, optional): Cesta ke konfiguračnímu souboru
        """
        super().__init__("config")
        self.config_file = config_file
        self._config = None

    def get_config(self):
        """
        Získání aktuální konfigurace

        Returns:
            dict: Aktuální konfigurace
        """
        if self._config is None:
            self._load_config()
        return self._config

    def _load_config(self):
        """
        Načtení konfigurace ze souboru
        """
        from config import load_config
        self._config = load_config(self.config_file)
        self.logger.debug("Konfigurace načtena")

    def update_config(self, new_config):
        """
        Aktualizace konfigurace

        Args:
            new_config (dict): Nová konfigurace

        Returns:
            dict: Aktualizovaná konfigurace
        """
        from config import update_config
        self._config = update_config(new_config, self.config_file)
        self.logger.info(f"Konfigurace aktualizována: {list(new_config.keys())}")
        return self._config

    def get_value(self, key, default=None):
        """
        Získání hodnoty z konfigurace

        Args:
            key (str): Klíč konfigurace
            default: Výchozí hodnota, pokud klíč neexistuje

        Returns:
            any: Hodnota konfigurace
        """
        if self._config is None:
            self._load_config()

        key_upper = key.upper()
        return self._config.get(key_upper, default)

    def set_value(self, key, value):
        """
        Nastavení hodnoty v konfiguraci

        Args:
            key (str): Klíč konfigurace
            value: Hodnota pro nastavení

        Returns:
            bool: True v případě úspěchu
        """
        key_upper = key.upper()

        if self._config is None:
            self._load_config()

        # Aktualizace hodnoty
        self._config[key_upper] = value

        # Uložení konfigurace
        from config import save_config
        result = save_config(self._config, self.config_file)

        if result:
            self.logger.info(f"Nastavena konfigurace {key} = {value}")
        else:
            self.logger.error(f"Chyba při nastavení konfigurace {key} = {value}")

        return result

    def reset_config(self):
        """
        Resetování konfigurace na výchozí hodnoty

        Returns:
            dict: Výchozí konfigurace
        """
        from config import DEFAULT_CONFIG, save_config
        self._config = DEFAULT_CONFIG.copy()
        save_config(self._config, self.config_file)
        self.logger.warning("Konfigurace resetována na výchozí hodnoty")
        return self._config

    def get_credentials(self):
        """
        Získání přihlašovacích údajů

        Returns:
            tuple: (username, password) nebo (None, None) pokud nejsou nastaveny
        """
        if self._config is None:
            self._load_config()

        username = self._config.get("USERNAME")
        password = self._config.get("PASSWORD")

        if not username or not password:
            self.logger.warning("Přihlašovací údaje nejsou nastaveny!")
            return None, None

        return username, password

    def export_config(self, include_password=False):
        """
        Export konfigurace pro zobrazení uživateli

        Args:
            include_password (bool): Zahrnout heslo v exportu

        Returns:
            dict: Konfigurace bez citlivých údajů
        """
        if self._config is None:
            self._load_config()

        # Vytvoření kopie konfigurace
        export_config = self._config.copy()

        # Odstranění hesla, pokud není požadováno
        if not include_password and "PASSWORD" in export_config:
            export_config["PASSWORD"] = "********"

        return export_config