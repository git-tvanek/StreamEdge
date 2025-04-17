#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SystemService - Služba pro správu a monitorování stavu systému
"""
import time
import logging
import os
import sys
import platform
from datetime import datetime
from Services.base.service_base import ServiceBase

logger = logging.getLogger(__name__)


class SystemService(ServiceBase):
    """
    Služba pro získávání informací o stavu systému a diagnostiku
    """

    def __init__(self, auth_service=None, cache_service=None):
        """
        Inicializace služby pro správu systému

        Args:
            auth_service (AuthService, optional): Instance služby pro autentizaci
            cache_service (CacheService, optional): Instance služby pro správu cache
        """
        super().__init__("system")
        self.auth_service = auth_service
        self.cache_service = cache_service
        self.start_time = datetime.now()

    def get_status(self):
        """
        Získání kompletního stavu systému

        Returns:
            dict: Stav systému, verzí, a komponent
        """
        status = {
            "status": "online",
            "version": self._get_config("APP_VERSION", "4.0.25-hf.0"),
            "language": self._get_config("LANGUAGE", "cz"),
            "uptime": self._get_uptime(),
            "system_info": self._get_system_info(),
            "cache": self._get_cache_info(),
            "auth": self._get_auth_status()
        }
        return status

    def _get_uptime(self):
        """
        Získání doby běhu aplikace

        Returns:
            dict: Informace o době běhu
        """
        uptime = datetime.now() - self.start_time
        return {
            "start_time": self.start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "seconds": uptime.total_seconds(),
            "formatted": str(uptime).split('.')[0]  # Remove microseconds
        }

    def _get_auth_status(self):
        """
        Získání stavu autentizace

        Returns:
            dict: Stav autentizace
        """
        if not self.auth_service:
            return {"status": "not_initialized"}

        token_valid = bool(self.auth_service.refresh_token)
        token_expires = 0

        if token_valid and self.auth_service.token_expires > 0:
            token_expires = int(self.auth_service.token_expires - time.time())
            token_valid = token_expires > 0

        return {
            "status": "authenticated" if token_valid else "not_authenticated",
            "token_valid": token_valid,
            "token_expires": token_expires,
            "language": self.auth_service.language
        }

    def _get_cache_info(self):
        """
        Získání informací o cache

        Returns:
            dict: Informace o cache
        """
        if self.cache_service:
            return self.cache_service.get_cache_info()

        # Import zde, abychom předešli cirkulárnímu importu
        try:
            from cache import get_cache_info
            return get_cache_info()
        except ImportError:
            return {"status": "unavailable"}

    def _get_system_info(self):
        """
        Získání informací o systému

        Returns:
            dict: Informace o systému
        """
        return {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "hostname": platform.node(),
            "cpu_count": os.cpu_count() or 0,
            "pid": os.getpid()
        }

    def clear_all_caches(self):
        """
        Vyčištění všech cache

        Returns:
            bool: True v případě úspěchu
        """
        if self.cache_service:
            return self.cache_service.clear_cache()

        # Import zde, abychom předešli cirkulárnímu importu
        try:
            from cache import clear_cache
            return clear_cache()
        except ImportError:
            logger.error("Cache modul není dostupný.")
            return False

    def restart_auth(self):
        """
        Restart autentizačního procesu - odhlášení a nové přihlášení

        Returns:
            bool: True v případě úspěchu
        """
        if not self.auth_service:
            logger.error("AuthService není dostupná.")
            return False

        # Nejprve se odhlásíme
        self.auth_service.logout()

        # Přihlásíme se znovu
        return self.auth_service.login()