#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CacheService - Služba pro správu cache
"""
import time
import logging
import threading
from Services.base.service_base import ServiceBase

logger = logging.getLogger(__name__)


class CacheService(ServiceBase):
    """
    Služba pro správu cache v aplikaci
    """

    def __init__(self):
        """
        Inicializace služby pro správu cache
        """
        super().__init__("cache")
        self._cache = {}
        self._cache_expiry = {}
        self._cache_lock = threading.Lock()
        self.initialize_cache()

    def initialize_cache(self):
        """
        Inicializace cache
        """
        with self._cache_lock:
            self._cache = {
                "channels": {},
                "streams": {},
                "epg": {},
                "devices": {}
            }
            self._cache_expiry = {}
        self.logger.debug("Cache inicializována")

    def get_from_cache(self, cache_key, fetch_function, *args, **kwargs):
        """
        Získání dat z cache nebo pomocí poskytnuté funkce

        Args:
            cache_key (str): Klíč cache
            fetch_function (callable): Funkce pro získání dat
            *args, **kwargs: Parametry pro funkci

        Returns:
            any: Data z cache nebo funkce
        """
        with self._cache_lock:
            # Kontrola cache
            if cache_key in self._cache and time.time() < self._cache_expiry.get(cache_key, 0):
                self.logger.debug(f"Data načtena z cache: {cache_key}")
                return self._cache[cache_key]

        # Získání dat
        data = fetch_function(*args, **kwargs)

        # Uložení do cache
        if data is not None:
            self.store_in_cache(cache_key, data)

        return data

    def store_in_cache(self, cache_key, data, cache_timeout=None):
        """
        Uložení dat do cache

        Args:
            cache_key (str): Klíč cache
            data (any): Data pro uložení
            cache_timeout (int, optional): Doba platnosti v sekundách nebo None pro výchozí hodnotu

        Returns:
            bool: True v případě úspěchu
        """
        with self._cache_lock:
            self._cache[cache_key] = data

            # Použití výchozí doby platnosti, pokud není zadána
            if cache_timeout is None:
                cache_timeout = self._get_config("CACHE_TIMEOUT", 3600)

            self._cache_expiry[cache_key] = time.time() + cache_timeout
            self.logger.debug(f"Data uložena do cache: {cache_key} (platnost: {cache_timeout}s)")
            return True

    def clear_cache(self, cache_key=None):
        """
        Vyčištění cache

        Args:
            cache_key (str, optional): Konkrétní klíč nebo None pro vyčištění všeho

        Returns:
            bool: True pokud byla cache vyčištěna
        """
        with self._cache_lock:
            if cache_key is None:
                # Vyčištění celé cache
                self.initialize_cache()
                self.logger.info("Celá cache byla vyčištěna")
            elif cache_key in self._cache:
                # Vyčištění konkrétní položky
                del self._cache[cache_key]
                if cache_key in self._cache_expiry:
                    del self._cache_expiry[cache_key]
                self.logger.info(f"Cache položka byla vyčištěna: {cache_key}")
            elif cache_key.endswith('*'):
                # Vyčištění položek začínajících daným prefixem
                prefix = cache_key[:-1]
                keys_to_delete = [k for k in self._cache.keys() if k.startswith(prefix)]
                for key in keys_to_delete:
                    del self._cache[key]
                    if key in self._cache_expiry:
                        del self._cache_expiry[key]
                self.logger.info(f"Cache položky s prefixem {prefix} byly vyčištěny ({len(keys_to_delete)} položek)")

        return True

    def get_cache_info(self):
        """
        Získání informací o cache

        Returns:
            dict: Informace o cache
        """
        with self._cache_lock:
            current_time = time.time()

            # Příprava informací o expiraci položek
            expires_in = {}
            expired_count = 0

            for key, expiry_time in self._cache_expiry.items():
                time_remaining = expiry_time - current_time
                if time_remaining > 0:
                    expires_in[key] = int(time_remaining)
                else:
                    expired_count += 1

            # Příprava informací o typu položek
            category_counts = {}
            for key in self._cache.keys():
                category = key.split('_')[0] if '_' in key else 'other'
                category_counts[category] = category_counts.get(category, 0) + 1

            return {
                "total_entries": len(self._cache),
                "expired_entries": expired_count,
                "categories": category_counts,
                "keys": list(self._cache.keys()),
                "expires_in": expires_in
            }

    def check_expired(self):
        """
        Kontrola a odstranění expirovaných položek

        Returns:
            int: Počet odstraněných položek
        """
        with self._cache_lock:
            current_time = time.time()
            expired_keys = [
                key for key, expiry_time in self._cache_expiry.items()
                if expiry_time < current_time
            ]

            # Odstranění expirovaných položek
            for key in expired_keys:
                if key in self._cache:
                    del self._cache[key]
                del self._cache_expiry[key]

            if expired_keys:
                self.logger.debug(f"Odstraněno {len(expired_keys)} expirovaných položek z cache")

            return len(expired_keys)