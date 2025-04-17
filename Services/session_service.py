#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SessionService - Služba pro správu HTTP sessions a requestů
"""
import logging
import requests
from urllib.parse import urlparse
from Services.base.service_base import ServiceBase
from Services.utils.constants import DEFAULT_USER_AGENT, TIME_CONSTANTS

logger = logging.getLogger(__name__)


class SessionService(ServiceBase):
    """
    Služba pro správu HTTP sessions a requestů
    """

    def __init__(self, user_agent=None):
        """
        Inicializace služby pro správu HTTP sessions

        Args:
            user_agent (str, optional): User-Agent hlavička nebo None pro výchozí
        """
        super().__init__("session")
        self.user_agent = user_agent or DEFAULT_USER_AGENT
        self.session = requests.Session()

        # Nastavení základních hlaviček
        self.session.headers.update({
            "User-Agent": self.user_agent
        })

    def get(self, url, params=None, headers=None, timeout=None, stream=False, allow_redirects=True):
        """
        Odeslání GET požadavku

        Args:
            url (str): URL
            params (dict, optional): Parametry požadavku
            headers (dict, optional): Hlavičky požadavku
            timeout (int, optional): Timeout v sekundách
            stream (bool): Použít streamování odpovědi
            allow_redirects (bool): Povolení přesměrování

        Returns:
            Response: Odpověď na požadavek nebo None při chybě
        """
        if timeout is None:
            timeout = TIME_CONSTANTS["DEFAULT_TIMEOUT"]

        # Výchozí hlavičky pro doménu
        request_headers = self._prepare_headers(url)

        # Přidání vlastních hlaviček
        if headers:
            request_headers.update(headers)

        try:
            response = self.session.get(
                url,
                params=params,
                headers=request_headers,
                timeout=timeout,
                stream=stream,
                allow_redirects=allow_redirects
            )

            # Kontrola HTTP statusu
            response.raise_for_status()
            return response

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Chyba při GET požadavku na {url}: {e}")
            return None

    def post(self, url, data=None, json=None, params=None, headers=None, timeout=None):
        """
        Odeslání POST požadavku

        Args:
            url (str): URL
            data (dict, optional): Formulářová data
            json (dict, optional): JSON data
            params (dict, optional): Parametry požadavku
            headers (dict, optional): Hlavičky požadavku
            timeout (int, optional): Timeout v sekundách

        Returns:
            Response: Odpověď na požadavek nebo None při chybě
        """
        if timeout is None:
            timeout = TIME_CONSTANTS["DEFAULT_TIMEOUT"]

        # Výchozí hlavičky pro doménu
        request_headers = self._prepare_headers(url)

        # Nastavení hlavičky Content-Type pro JSON data
        if json and "Content-Type" not in request_headers:
            request_headers["Content-Type"] = "application/json"

        # Přidání vlastních hlaviček
        if headers:
            request_headers.update(headers)

        try:
            response = self.session.post(
                url,
                data=data,
                json=json,
                params=params,
                headers=request_headers,
                timeout=timeout
            )

            # Kontrola HTTP statusu
            response.raise_for_status()
            return response

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Chyba při POST požadavku na {url}: {e}")
            return None

    def proxy_request(self, url, headers=None, stream=True):
        """
        Proxy požadavek

        Args:
            url (str): URL pro proxy
            headers (dict, optional): Hlavičky
            stream (bool): Použít streamování odpovědi

        Returns:
            Response: Odpověď na požadavek nebo None při chybě
        """
        if not url.startswith('http'):
            url = 'https://' + url

        return self.get(url, headers=headers, stream=stream)

    def get_redirect_url(self, url, headers=None, timeout=None):
        """
        Získání cílové URL po přesměrování

        Args:
            url (str): Výchozí URL
            headers (dict, optional): Hlavičky pro požadavek
            timeout (int, optional): Timeout v sekundách

        Returns:
            str: Cílová URL po přesměrování nebo None při chybě
        """
        if timeout is None:
            timeout = TIME_CONSTANTS["STREAM_TIMEOUT"]

        response = self.get(url, headers=headers, allow_redirects=False, timeout=timeout)

        if not response:
            return None

        # Získání cílové URL z hlavičky Location
        if response.status_code in (301, 302, 303, 307, 308):
            return response.headers.get("Location", url)

        return url

    def get_json(self, url, params=None, headers=None, timeout=None):
        """
        Odeslání GET požadavku a parsování JSON odpovědi

        Args:
            url (str): URL
            params (dict, optional): Parametry požadavku
            headers (dict, optional): Hlavičky požadavku
            timeout (int, optional): Timeout v sekundách

        Returns:
            dict: Parsovaná JSON odpověď nebo None při chybě
        """
        response = self.get(url, params=params, headers=headers, timeout=timeout)

        if not response:
            return None

        try:
            return response.json()
        except ValueError as e:
            self.logger.error(f"Chyba při parsování JSON odpovědi: {e}")
            return None

    def post_json(self, url, data=None, json=None, params=None, headers=None, timeout=None):
        """
        Odeslání POST požadavku a parsování JSON odpovědi

        Args:
            url (str): URL
            data (dict, optional): Formulářová data
            json (dict, optional): JSON data
            params (dict, optional): Parametry požadavku
            headers (dict, optional): Hlavičky požadavku
            timeout (int, optional): Timeout v sekundách

        Returns:
            dict: Parsovaná JSON odpověď nebo None při chybě
        """
        response = self.post(url, data=data, json=json, params=params, headers=headers, timeout=timeout)

        if not response:
            return None

        try:
            return response.json()
        except ValueError as e:
            self.logger.error(f"Chyba při parsování JSON odpovědi: {e}")
            return None

    def _prepare_headers(self, url):
        """
        Příprava hlaviček na základě URL

        Args:
            url (str): URL

        Returns:
            dict: Hlavičky přizpůsobené pro danou URL
        """
        headers = {}

        # Přidání Host hlavičky
        try:
            parsed_url = urlparse(url)
            if parsed_url.netloc:
                headers["Host"] = parsed_url.netloc
        except Exception:
            pass

        # Přidání User-Agent
        headers["User-Agent"] = self.user_agent

        return headers

    def close(self):
        """
        Uzavření session
        """
        self.session.close()
        self.logger.debug("HTTP session uzavřena")