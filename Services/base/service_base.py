#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ServiceBase - Základní třída pro všechny služby MagentaTV/MagioTV
"""
import logging
from abc import ABC
from flask import current_app

from Services.utils.http_client import MagentaHTTPClient
from Services.utils.constants import BASE_URLS, DEFAULT_USER_AGENT

logger = logging.getLogger(__name__)


class ServiceBase(ABC):
    """
    Základní abstraktní třída pro všechny služby

    Poskytuje základní funkcionalitu, kterou používají všechny služby:
    - logger pro logování
    - přístup ke konfiguraci
    - základní HTTP klient
    """

    def __init__(self, service_name):
        """
        Inicializace základní služby

        Args:
            service_name (str): Název služby pro účely logování
        """
        self.service_name = service_name
        self.logger = logging.getLogger(f"{__name__}.{service_name}")
        self.logger.debug(f"Inicializace služby {service_name}")

        # Možnost použít vlastní HTTP klient
        self._http_client = None

    def _get_config(self, key, default=None):
        """
        Získání hodnoty z konfigurace aplikace

        Args:
            key (str): Klíč konfigurace
            default: Výchozí hodnota, pokud klíč neexistuje

        Returns:
            any: Hodnota konfigurace nebo výchozí hodnota
        """
        try:
            return current_app.config.get(key.upper(), default)
        except RuntimeError:
            # Fallback pokud není aktivní aplikační kontext
            self.logger.warning(f"Nelze získat konfiguraci pro {key}, použije se výchozí hodnota")
            return default

    def _create_http_client(self, base_url=None, language="cz", user_agent=None):
        """
        Vytvoření HTTP klienta

        Args:
            base_url (str, optional): Základní URL nebo None pro generování podle jazyka
            language (str): Kód jazyka (cz, sk)
            user_agent (str, optional): User-Agent hlavička nebo None pro výchozí

        Returns:
            MagentaHTTPClient: Instance HTTP klienta
        """
        # Pokud již existuje klient, vrátíme ho
        if self._http_client:
            return self._http_client

        # Určení základní URL podle jazyka, pokud není zadána
        if base_url is None:
            language_lower = language.lower()
            base_url = BASE_URLS.get(language_lower, f"https://{language_lower}go.magio.tv")

        # Vytvoření klienta
        self._http_client = MagentaHTTPClient(
            base_url=base_url,
            language=language,
            user_agent=user_agent or DEFAULT_USER_AGENT
        )

        return self._http_client

    def _close_http_client(self):
        """
        Uzavření HTTP klienta
        """
        if self._http_client:
            self._http_client.close()
            self._http_client = None