#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTTP klient pro komunikaci s MagentaTV/MagioTV API

Tento modul poskytuje rozšířenou funkcionalitu pro HTTP požadavky
určené specificky pro komunikaci s MagentaTV/MagioTV API.
"""
import requests
import logging
from urllib.parse import urlparse
from Services.utils.constants import DEFAULT_USER_AGENT, TIME_CONSTANTS

logger = logging.getLogger(__name__)


class MagentaHTTPClient:
    """
    HTTP klient pro komunikaci s MagentaTV/MagioTV API

    Poskytuje metody pro snadnější komunikaci s API, včetně
    automatického přidávání hlaviček a zpracování odpovědí.
    """

    def __init__(self, base_url, language="cz", user_agent=None):
        """
        Inicializace HTTP klienta

        Args:
            base_url (str): Základní URL pro API požadavky
            language (str): Kód jazyka (cz, sk)
            user_agent (str, optional): User-Agent hlavička nebo None pro výchozí
        """
        self.base_url = base_url
        self.language = language.lower()
        self.user_agent = user_agent or DEFAULT_USER_AGENT
        self.session = requests.Session()

        # Základní hlavičky pro všechny požadavky
        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Host": urlparse(self.base_url).netloc
        })

    def get(self, endpoint, params=None, headers=None, timeout=None):
        """
        Odeslání GET požadavku

        Args:
            endpoint (str): Cílový endpoint (bez základní URL)
            params (dict, optional): Parametry pro požadavek
            headers (dict, optional): Dodatečné hlavičky
            timeout (int, optional): Timeout v sekundách nebo None pro výchozí

        Returns:
            dict: JSON odpověď nebo None v případě chyby
        """
        url = f"{self.base_url}{endpoint}"
        timeout = timeout or TIME_CONSTANTS["DEFAULT_TIMEOUT"]

        try:
            response = self.session.get(
                url,
                params=params,
                headers=headers,
                timeout=timeout
            )

            # Kontrola HTTP statusu
            response.raise_for_status()

            # Pokud je odpověď prázdná, vrátíme None
            if not response.content:
                return None

            # Parsování JSON odpovědi
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Chyba při GET požadavku na {url}: {e}")
            return None

    def post(self, endpoint, json=None, data=None, params=None, headers=None, timeout=None):
        """
        Odeslání POST požadavku

        Args:
            endpoint (str): Cílový endpoint (bez základní URL)
            json (dict, optional): JSON data pro požadavek
            data (dict, optional): Formulářová data pro požadavek
            params (dict, optional): Parametry pro požadavek
            headers (dict, optional): Dodatečné hlavičky
            timeout (int, optional): Timeout v sekundách nebo None pro výchozí

        Returns:
            dict: JSON odpověď nebo None v případě chyby
        """
        url = f"{self.base_url}{endpoint}"
        timeout = timeout or TIME_CONSTANTS["DEFAULT_TIMEOUT"]

        # Nastavení hlavičky Content-Type pro JSON data
        if json and not headers:
            headers = {"Content-Type": "application/json"}
        elif json and headers and "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"

        try:
            response = self.session.post(
                url,
                json=json,
                data=data,
                params=params,
                headers=headers,
                timeout=timeout
            )

            # Kontrola HTTP statusu
            response.raise_for_status()

            # Pokud je odpověď prázdná, vrátíme None
            if not response.content:
                return None

            # Parsování JSON odpovědi
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Chyba při POST požadavku na {url}: {e}")
            return None

    def get_redirect_url(self, url, headers=None, timeout=None):
        """
        Získání cílové URL po přesměrování

        Args:
            url (str): Výchozí URL
            headers (dict, optional): Hlavičky pro požadavek
            timeout (int, optional): Timeout v sekundách nebo None pro výchozí

        Returns:
            str: Cílová URL po přesměrování nebo None v případě chyby
        """
        timeout = timeout or TIME_CONSTANTS["STREAM_TIMEOUT"]

        try:
            response = self.session.get(
                url,
                headers=headers,
                allow_redirects=False,
                timeout=timeout
            )

            # Získání cílové URL z hlavičky Location
            if response.status_code in (301, 302, 303, 307, 308):
                return response.headers.get("Location", url)

            return url

        except requests.exceptions.RequestException as e:
            logger.error(f"Chyba při získání redirect URL pro {url}: {e}")
            return None

    def close(self):
        """
        Uzavření session
        """
        self.session.close()