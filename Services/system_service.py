#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SystemService - Služba pro správu a monitorování stavu systému

Tato služba poskytuje funkce pro monitorování stavu systému, správu
a diagnostiku různých komponent aplikace. Centralizuje sběr informací
o běžících službách, sleduje chyby a poskytuje přehled o stavu systému.
"""
import time
import logging
import os
import sys
import platform
import json
from datetime import datetime, timedelta
from threading import Lock
from Services.base.service_base import ServiceBase

logger = logging.getLogger(__name__)


class SystemService(ServiceBase):
    """
    Služba pro získávání informací o stavu systému a diagnostiku

    Poskytuje centrální bod pro monitoring systému, logování
    událostí a správu systémových parametrů.
    """

    def __init__(self, auth_service=None, cache_service=None, config_service=None):
        """
        Inicializace služby pro správu systému

        Args:
            auth_service (AuthService, optional): Instance služby pro autentizaci
            cache_service (CacheService, optional): Instance služby pro správu cache
            config_service (ConfigService, optional): Instance služby pro konfiguraci
        """
        super().__init__("system")
        self.auth_service = auth_service
        self.cache_service = cache_service
        self.config_service = config_service
        self.start_time = datetime.now()

        # Monitoring
        self.services = {}  # Registrované služby
        self.errors = []  # Poslední chyby
        self.events = []  # Události systému
        self.max_errors = 100  # Maximální počet chyb v historii
        self.max_events = 200  # Maximální počet událostí v historii

        # Zámek pro přístup k historii chyb a událostí
        self._history_lock = Lock()

        # Inicializace logovacího souboru
        self._init_system_log()

        self.logger.info("SystemService inicializován")

        # Zaznamenání události startu
        self.log_event("system", "startup", "Systém byl spuštěn")

    def _init_system_log(self):
        """
        Inicializace logovacího souboru pro systémové události
        """
        try:
            # Získání adresáře pro logy
            if self.config_service:
                log_dir = self.config_service.get_value("LOG_DIR", "logs")
            else:
                log_dir = "logs"

            # Vytvoření adresáře, pokud neexistuje
            os.makedirs(log_dir, exist_ok=True)

            # Cesta k logovacímu souboru
            self.system_log_file = os.path.join(log_dir, "system.log")

            # Kontrola a rotace logu
            self._rotate_log_file()
        except Exception as e:
            self.logger.error(f"Chyba při inicializaci systémového logu: {e}")

    def _rotate_log_file(self):
        """
        Rotace logovacího souboru, pokud je příliš velký
        """
        try:
            # Max velikost logu (10 MB)
            max_size = 10 * 1024 * 1024

            # Pokud soubor existuje a je větší než max_size
            if os.path.exists(self.system_log_file) and os.path.getsize(self.system_log_file) > max_size:
                # Přejmenování souboru s časovou značkou
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = f"{self.system_log_file}.{timestamp}"
                os.rename(self.system_log_file, backup_file)

                # Záznam o rotaci
                self.logger.info(f"Systémový log byl rotován: {backup_file}")
        except Exception as e:
            self.logger.error(f"Chyba při rotaci logovacího souboru: {e}")

    def register_service(self, service_name, service_instance):
        """
        Registrace služby pro monitoring

        Args:
            service_name (str): Název služby
            service_instance (object): Instance služby

        Returns:
            bool: True pokud byla služba úspěšně registrována
        """
        self.services[service_name] = {
            "instance": service_instance,
            "registered_at": datetime.now(),
            "status": "active"
        }

        self.logger.debug(f"Služba '{service_name}' byla registrována pro monitoring")
        return True

    def register_auth_service(self, auth_service):
        """
        Registrace AuthService pro monitoring

        Args:
            auth_service (AuthService): Instance služby pro autentizaci

        Returns:
            bool: True pokud byla služba úspěšně registrována
        """
        self.auth_service = auth_service
        return self.register_service("auth", auth_service)

    def update_auth_status(self):
        """
        Aktualizace stavu autentizace v systémovém monitoringu

        Returns:
            dict: Aktuální stav autentizace
        """
        if not self.auth_service:
            return {"status": "not_initialized"}

        # Získání stavu autentizace
        auth_status = self.auth_service.get_auth_status()

        # Aktualizace informací v monitoringu
        if "auth" in self.services:
            self.services["auth"]["last_updated"] = datetime.now()
            self.services["auth"]["auth_status"] = auth_status

            # Zaznamenání události
            if auth_status["authenticated"]:
                self.log_event("auth", "token_updated", "Autentizační token byl aktualizován")
            else:
                self.log_event("auth", "auth_failed", "Autentizace není aktivní")

        return auth_status

    def log_error(self, service_name, error_message, error_details=None):
        """
        Zaznamenání chyby do systémového logu

        Args:
            service_name (str): Název služby, která hlásí chybu
            error_message (str): Text chybové zprávy
            error_details (str, optional): Detailní informace o chybě

        Returns:
            bool: True pokud byla chyba zaznamenána
        """
        with self._history_lock:
            # Vytvoření záznamu o chybě
            error_entry = {
                "timestamp": datetime.now(),
                "service": service_name,
                "message": error_message,
                "details": error_details
            }

            # Přidání do historie chyb
            self.errors.append(error_entry)

            # Omezení délky historie
            if len(self.errors) > self.max_errors:
                self.errors = self.errors[-self.max_errors:]

            # Zápis do logovacího souboru
            self._write_to_system_log(
                "ERROR",
                f"[{service_name}] {error_message}" +
                (f" - {error_details}" if error_details else "")
            )

        # Logování přes standardní logger
        self.logger.error(f"[{service_name}] {error_message}" +
                          (f" - {error_details}" if error_details else ""))

        return True

    def log_event(self, service_name, event_type, event_message, event_data=None):
        """
        Zaznamenání události do systémového logu

        Args:
            service_name (str): Název služby, která hlásí událost
            event_type (str): Typ události (např. 'startup', 'shutdown', 'config_change')
            event_message (str): Text zprávy o události
            event_data (dict, optional): Dodatečná data k události

        Returns:
            bool: True pokud byla událost zaznamenána
        """
        with self._history_lock:
            # Vytvoření záznamu o události
            event_entry = {
                "timestamp": datetime.now(),
                "service": service_name,
                "type": event_type,
                "message": event_message,
                "data": event_data
            }

            # Přidání do historie událostí
            self.events.append(event_entry)

            # Omezení délky historie
            if len(self.events) > self.max_events:
                self.events = self.events[-self.max_events:]

            # Zápis do logovacího souboru
            self._write_to_system_log(
                "EVENT",
                f"[{service_name}] {event_type}: {event_message}"
            )

        # Logování přes standardní logger
        self.logger.info(f"[{service_name}] {event_type}: {event_message}")

        return True

    def _write_to_system_log(self, log_type, message):
        """
        Zápis zprávy do systémového logovacího souboru

        Args:
            log_type (str): Typ záznamu ('ERROR', 'EVENT', 'INFO', atd.)
            message (str): Text zprávy
        """
        try:
            # Formátování záznamu
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"{timestamp} [{log_type}] {message}\n"

            # Zápis do souboru
            with open(self.system_log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)

        except Exception as e:
            # Pokud se nepodaří zapsat do souboru, použijeme standardní logger
            self.logger.error(f"Chyba při zápisu do systémového logu: {e}")

    def get_status(self):
        """
        Získání kompletního stavu systému

        Returns:
            dict: Stav systému, verzí, a komponent
        """
        # Základní informace o systému
        status = {
            "status": "online",
            "version": self._get_config("APP_VERSION", "4.0.25-hf.0"),
            "language": self._get_config("LANGUAGE", "cz"),
            "uptime": self._get_uptime(),
            "system_info": self._get_system_info(),
            "services": self._get_services_status(),
            "cache": self._get_cache_info(),
            "auth": self._get_auth_status(),
            "error_count": len(self.errors),
            "event_count": len(self.events)
        }

        # Zaznamenání události
        self.log_event("system", "status_check", "Status systému byl zkontrolován")

        return status

    def _get_services_status(self):
        """
        Získání stavu registrovaných služeb

        Returns:
            dict: Stav služeb
        """
        services_status = {}

        for name, service_info in self.services.items():
            # Základní informace o službě
            service_status = {
                "status": service_info.get("status", "unknown"),
                "registered_at": service_info.get("registered_at", datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
            }

            # Přidání dalších informací, pokud jsou k dispozici
            if "last_updated" in service_info:
                service_status["last_updated"] = service_info["last_updated"].strftime("%Y-%m-%d %H:%M:%S")

            if "auth_status" in service_info:
                service_status["auth_status"] = service_info["auth_status"]

            services_status[name] = service_status

        return services_status

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

        # Pokud je k dispozici nová metoda get_auth_status
        if hasattr(self.auth_service, "get_auth_status") and callable(getattr(self.auth_service, "get_auth_status")):
            return self.auth_service.get_auth_status()

        # Kompatibilita se starší verzí
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
            # Pokud je k dispozici metoda get_cache_info
            if hasattr(self.cache_service, "get_cache_info") and callable(
                    getattr(self.cache_service, "get_cache_info")):
                return self.cache_service.get_cache_info()
            else:
                return {"status": "available", "details_unavailable": True}

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
            "pid": os.getpid(),
            "memory_info": self._get_memory_info(),
            "timezone": datetime.now().astimezone().tzinfo.tzname(datetime.now())
        }

    def _get_memory_info(self):
        """
        Získání informací o využití paměti

        Returns:
            dict: Informace o paměti
        """
        try:
            import psutil
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()

            return {
                "rss": memory_info.rss,  # Resident Set Size
                "rss_mb": round(memory_info.rss / (1024 * 1024), 2),  # MB
                "vms": memory_info.vms,  # Virtual Memory Size
                "vms_mb": round(memory_info.vms / (1024 * 1024), 2)  # MB
            }
        except (ImportError, Exception):
            # Pokud není k dispozici psutil nebo nastane jiná chyba
            return {"available": False}

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
            self.logger.error("AuthService není dostupná.")
            return False

        # Zaznamenání události
        self.log_event("system", "auth_restart", "Restart autentizačního procesu")

        # Nejprve se odhlásíme
        self.auth_service.logout()

        # Přihlásíme se znovu
        success = self.auth_service.login()

        # Zaznamenání výsledku
        if success:
            self.log_event("system", "auth_restart_success", "Restart autentizace úspěšný")
        else:
            self.log_error("system", "Restart autentizace selhal")

        return success

    def get_errors(self, limit=10, service=None, since=None):
        """
        Získání posledních chyb ze systémového logu

        Args:
            limit (int): Maximální počet chyb k vrácení
            service (str, optional): Filtrování podle služby
            since (datetime, optional): Filtrování od daného data a času

        Returns:
            list: Seznam chyb
        """
        with self._history_lock:
            filtered_errors = self.errors.copy()

            # Filtrování podle služby
            if service:
                filtered_errors = [e for e in filtered_errors if e["service"] == service]

            # Filtrování podle času
            if since:
                filtered_errors = [e for e in filtered_errors if e["timestamp"] >= since]

            # Omezení počtu a konverze času na string
            result = []
            for error in filtered_errors[-limit:]:
                error_copy = error.copy()
                error_copy["timestamp"] = error_copy["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                result.append(error_copy)

            return result

    def get_events(self, limit=20, service=None, event_type=None, since=None):
        """
        Získání posledních událostí ze systémového logu

        Args:
            limit (int): Maximální počet událostí k vrácení
            service (str, optional): Filtrování podle služby
            event_type (str, optional): Filtrování podle typu události
            since (datetime, optional): Filtrování od daného data a času

        Returns:
            list: Seznam událostí
        """
        with self._history_lock:
            filtered_events = self.events.copy()

            # Filtrování podle služby
            if service:
                filtered_events = [e for e in filtered_events if e["service"] == service]

            # Filtrování podle typu
            if event_type:
                filtered_events = [e for e in filtered_events if e["type"] == event_type]

            # Filtrování podle času
            if since:
                filtered_events = [e for e in filtered_events if e["timestamp"] >= since]

            # Omezení počtu a konverze času na string
            result = []
            for event in filtered_events[-limit:]:
                event_copy = event.copy()
                event_copy["timestamp"] = event_copy["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                result.append(event_copy)

            return result

    def export_system_logs(self, days=7):
        """
        Export systémových logů za posledních X dní

        Args:
            days (int): Počet dní zpět pro export

        Returns:
            dict: Exportovaná data nebo informace o chybě
        """
        try:
            # Časové omezení
            since = datetime.now() - timedelta(days=days)

            # Export chyb a událostí
            export_data = {
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "period_days": days,
                "system_info": self._get_system_info(),
                "errors": self.get_errors(limit=1000, since=since),
                "events": self.get_events(limit=1000, since=since),
                "services": self._get_services_status(),
                "auth_status": self._get_auth_status(),
                "cache_status": self._get_cache_info()
            }

            return export_data

        except Exception as e:
            self.logger.error(f"Chyba při exportu systémových logů: {e}")
            return {"error": str(e), "success": False}

    def get_service_health(self):
        """
        Zjištění zdraví všech registrovaných služeb

        Returns:
            dict: Stav zdraví služeb a systému
        """
        health = {
            "system": "healthy",
            "services": {}
        }

        # Kontrola všech registrovaných služeb
        for name, service_info in self.services.items():
            service_status = service_info.get("status", "unknown")

            # Specifická kontrola pro AuthService
            if name == "auth" and self.auth_service:
                try:
                    auth_status = self.auth_service.get_auth_status()
                    is_healthy = auth_status.get("authenticated", False)
                    health["services"]["auth"] = "healthy" if is_healthy else "degraded"
                except Exception:
                    health["services"]["auth"] = "unhealthy"
            # Kontrola CacheService
            elif name == "cache" and self.cache_service:
                try:
                    cache_info = self.cache_service.get_cache_info()
                    is_healthy = cache_info and not cache_info.get("error", False)
                    health["services"]["cache"] = "healthy" if is_healthy else "degraded"
                except Exception:
                    health["services"]["cache"] = "unhealthy"
            # Kontrola ConfigService
            elif name == "config" and self.config_service:
                try:
                    config_info = self.config_service.get_config()
                    is_healthy = bool(config_info)
                    health["services"]["config"] = "healthy" if is_healthy else "degraded"
                except Exception:
                    health["services"]["config"] = "unhealthy"
            # Obecná kontrola
            else:
                health["services"][name] = service_status if service_status in ["healthy", "degraded",
                                                                                "unhealthy"] else "unknown"

        # Celkové zdraví systému
        service_states = list(health["services"].values())
        if "unhealthy" in service_states:
            health["system"] = "unhealthy"
        elif "degraded" in service_states:
            health["system"] = "degraded"

        return health