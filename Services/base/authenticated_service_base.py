#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AuthenticatedServiceBase - Základní třída pro služby vyžadující autentizaci
"""
import logging
from Services.base.service_base import ServiceBase

logger = logging.getLogger(__name__)


class AuthenticatedServiceBase(ServiceBase):
    """
    Základní třída pro služby vyžadující autentizaci

    Rozšiřuje ServiceBase o přístup k autentizační službě.
    """

    def __init__(self, service_name, auth_service):
        """
        Inicializace služby vyžadující autentizaci

        Args:
            service_name (str): Název služby pro účely logování
            auth_service (AuthService): Instance služby pro autentizaci
        """
        super().__init__(service_name)
        self.auth_service = auth_service

    def _check_auth(self):
        """
        Kontrola autentizace

        Returns:
            bool: True pokud je uživatel přihlášen
        """
        if not self.auth_service:
            self.logger.error("AuthService není k dispozici")
            return False

        return self.auth_service.refresh_access_token()

    def _get_auth_headers(self):
        """
        Získání autorizačních hlaviček

        Returns:
            dict: Hlavičky s autorizačním tokenem nebo None při chybě
        """
        if not self._check_auth():
            return None

        return self.auth_service.get_auth_headers()