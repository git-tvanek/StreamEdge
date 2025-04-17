#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ServiceFactory - Továrna pro vytváření služeb MagentaTV/MagioTV
"""
import logging
from flask import current_app

from Services.auth_service import AuthService
from Services.channel_service import ChannelService
from Services.stream_service import StreamService
from Services.epg_service import EPGService
from Services.device_service import DeviceService
from Services.playlist_service import PlaylistService
from Services.catchup_service import CatchupService
from Services.client_service import ClientService
from Services.system_service import SystemService
from Services.config_service import ConfigService
from Services.cache_service import CacheService
from Services.session_service import SessionService

logger = logging.getLogger(__name__)


class ServiceFactory:
    """
    Továrna pro vytváření instancí služeb

    Tato třída zajišťuje vytváření instancí jednotlivých služeb
    s příslušnou konfigurací a zajišťuje jejich správné propojení.
    """

    _instances = {}

    @classmethod
    def create_system_service(cls, auth_service=None, cache_service=None):
        """
        Vytvoření instance SystemService

        Args:
            auth_service (AuthService, optional): Instance služby pro autentizaci
            cache_service (CacheService, optional): Instance služby pro správu cache

        Returns:
            SystemService: Instance služby pro správu systému
        """
        # Použití existujících služeb nebo vytvoření nových
        if auth_service is None:
            auth_service = cls.create_auth_service()
        if cache_service is None:
            cache_service = cls.create_cache_service()

        # Vytvoření klíče pro instanci
        instance_key = f"system_{id(auth_service)}_{id(cache_service)}"

        # Kontrola, zda instance již existuje
        if instance_key in cls._instances:
            return cls._instances[instance_key]

        # Vytvoření nové instance
        system_service = SystemService(auth_service, cache_service)
        cls._instances[instance_key] = system_service
        return system_service

    @classmethod
    def create_config_service(cls, config_file=None):
        """
        Vytvoření instance ConfigService

        Args:
            config_file (str, optional): Cesta ke konfiguračnímu souboru

        Returns:
            ConfigService: Instance služby pro správu konfigurace
        """
        # Vytvoření klíče pro instanci
        instance_key = f"config_{config_file}"

        # Kontrola, zda instance již existuje
        if instance_key in cls._instances:
            return cls._instances[instance_key]

        # Vytvoření nové instance
        config_service = ConfigService(config_file)
        cls._instances[instance_key] = config_service
        return config_service

    @classmethod
    def create_cache_service(cls):
        """
        Vytvoření instance CacheService

        Returns:
            CacheService: Instance služby pro správu cache
        """
        # Vytvoření klíče pro instanci
        instance_key = "cache"

        # Kontrola, zda instance již existuje
        if instance_key in cls._instances:
            return cls._instances[instance_key]

        # Vytvoření nové instance
        cache_service = CacheService()
        cls._instances[instance_key] = cache_service
        return cache_service

    @classmethod
    def create_session_service(cls, user_agent=None):
        """
        Vytvoření instance SessionService

        Args:
            user_agent (str, optional): User-Agent hlavička

        Returns:
            SessionService: Instance služby pro správu HTTP sessions
        """
        # Použití konfigurace pro User-Agent, pokud není zadán
        if user_agent is None:
            try:
                from Services.utils.constants import DEFAULT_USER_AGENT
                user_agent = DEFAULT_USER_AGENT
            except ImportError:
                pass

        # Vytvoření klíče pro instanci
        instance_key = f"session_{user_agent}"

        # Kontrola, zda instance již existuje
        if instance_key in cls._instances:
            return cls._instances[instance_key]

        # Vytvoření nové instance
        session_service = SessionService(user_agent)
        cls._instances[instance_key] = session_service
        return session_service

    @classmethod
    def create_auth_service(cls, username=None, password=None, language=None,
                            session_service=None, config_service=None):
        """
        Vytvoření instance AuthService

        Args:
            username (str, optional): Přihlašovací jméno nebo None pro načtení z konfigurace
            password (str, optional): Heslo nebo None pro načtení z konfigurace
            language (str, optional): Kód jazyka (cz, sk) nebo None pro načtení z konfigurace
            session_service (SessionService, optional): Instance služby pro HTTP komunikaci
            config_service (ConfigService, optional): Instance služby pro konfiguraci

        Returns:
            AuthService: Instance služby pro autentizaci
        """
        # Načtení konfigurace, pokud nejsou parametry zadány
        if config_service is None:
            config_service = cls.create_config_service()

        if username is None:
            username = config_service.get_value("USERNAME", "")
        if password is None:
            password = config_service.get_value("PASSWORD", "")
        if language is None:
            language = config_service.get_value("LANGUAGE", "cz")

        # Získání nebo vytvoření SessionService
        if session_service is None:
            session_service = cls.create_session_service()

        # Vytvoření klíče pro instanci
        instance_key = f"auth_{username}_{language}"

        # Kontrola, zda instance již existuje
        if instance_key in cls._instances:
            return cls._instances[instance_key]

        # Vytvoření nové instance
        auth_service = AuthService(username, password, language)
        cls._instances[instance_key] = auth_service
        return auth_service

    @classmethod
    def create_channel_service(cls, auth_service=None, cache_service=None, session_service=None):
        """
        Vytvoření instance ChannelService

        Args:
            auth_service (AuthService, optional): Instance služby pro autentizaci nebo None pro vytvoření nové
            cache_service (CacheService, optional): Instance služby pro cache
            session_service (SessionService, optional): Instance služby pro HTTP komunikaci

        Returns:
            ChannelService: Instance služby pro kanály
        """
        # Získání nebo vytvoření závislostí
        if auth_service is None:
            auth_service = cls.create_auth_service()
        if cache_service is None:
            cache_service = cls.create_cache_service()
        if session_service is None:
            session_service = cls.create_session_service()

        # Vytvoření klíče pro instanci
        instance_key = f"channel_{id(auth_service)}"

        # Kontrola, zda instance již existuje
        if instance_key in cls._instances:
            return cls._instances[instance_key]

        # Vytvoření nové instance
        channel_service = ChannelService(auth_service)
        cls._instances[instance_key] = channel_service
        return channel_service

    @classmethod
    def create_stream_service(cls, auth_service=None, cache_service=None, session_service=None, quality=None):
        """
        Vytvoření instance StreamService

        Args:
            auth_service (AuthService, optional): Instance služby pro autentizaci nebo None pro vytvoření nové
            cache_service (CacheService, optional): Instance služby pro cache
            session_service (SessionService, optional): Instance služby pro HTTP komunikaci
            quality (str, optional): Kvalita streamu (p1-p5) nebo None pro načtení z konfigurace

        Returns:
            StreamService: Instance služby pro streamy
        """
        # Získání nebo vytvoření závislostí
        if auth_service is None:
            auth_service = cls.create_auth_service()
        if cache_service is None:
            cache_service = cls.create_cache_service()
        if session_service is None:
            session_service = cls.create_session_service()

        # Načtení kvality z konfigurace, pokud není zadána
        if quality is None:
            # Vytvoření ConfigService pro načtení konfigurace
            config_service = cls.create_config_service()
            quality = config_service.get_value("QUALITY", "p5")

        # Vytvoření klíče pro instanci
        instance_key = f"stream_{id(auth_service)}_{quality}"

        # Kontrola, zda instance již existuje
        if instance_key in cls._instances:
            return cls._instances[instance_key]

        # Vytvoření nové instance
        stream_service = StreamService(auth_service, quality)
        cls._instances[instance_key] = stream_service
        return stream_service

    @classmethod
    def create_epg_service(cls, auth_service=None, cache_service=None, session_service=None):
        """
        Vytvoření instance EPGService

        Args:
            auth_service (AuthService, optional): Instance služby pro autentizaci nebo None pro vytvoření nové
            cache_service (CacheService, optional): Instance služby pro cache
            session_service (SessionService, optional): Instance služby pro HTTP komunikaci

        Returns:
            EPGService: Instance služby pro EPG
        """
        # Získání nebo vytvoření závislostí
        if auth_service is None:
            auth_service = cls.create_auth_service()
        if cache_service is None:
            cache_service = cls.create_cache_service()
        if session_service is None:
            session_service = cls.create_session_service()

        # Vytvoření klíče pro instanci
        instance_key = f"epg_{id(auth_service)}"

        # Kontrola, zda instance již existuje
        if instance_key in cls._instances:
            return cls._instances[instance_key]

        # Vytvoření nové instance
        epg_service = EPGService(auth_service)
        cls._instances[instance_key] = epg_service
        return epg_service

    @classmethod
    def create_device_service(cls, auth_service=None, cache_service=None, session_service=None):
        """
        Vytvoření instance DeviceService

        Args:
            auth_service (AuthService, optional): Instance služby pro autentizaci nebo None pro vytvoření nové
            cache_service (CacheService, optional): Instance služby pro cache
            session_service (SessionService, optional): Instance služby pro HTTP komunikaci

        Returns:
            DeviceService: Instance služby pro zařízení
        """
        # Získání nebo vytvoření závislostí
        if auth_service is None:
            auth_service = cls.create_auth_service()
        if cache_service is None:
            cache_service = cls.create_cache_service()
        if session_service is None:
            session_service = cls.create_session_service()

        # Vytvoření klíče pro instanci
        instance_key = f"device_{id(auth_service)}"

        # Kontrola, zda instance již existuje
        if instance_key in cls._instances:
            return cls._instances[instance_key]

        # Vytvoření nové instance
        device_service = DeviceService(auth_service)
        cls._instances[instance_key] = device_service
        return device_service

    @classmethod
    def create_catchup_service(cls, auth_service=None, epg_service=None, cache_service=None,
                               session_service=None, quality=None):
        """
        Vytvoření instance CatchupService

        Args:
            auth_service (AuthService, optional): Instance služby pro autentizaci nebo None pro vytvoření nové
            epg_service (EPGService, optional): Instance služby pro EPG nebo None pro vytvoření nové
            cache_service (CacheService, optional): Instance služby pro cache
            session_service (SessionService, optional): Instance služby pro HTTP komunikaci
            quality (str, optional): Kvalita streamu (p1-p5) nebo None pro načtení z konfigurace

        Returns:
            CatchupService: Instance služby pro archiv
        """
        # Získání nebo vytvoření závislostí
        if auth_service is None:
            auth_service = cls.create_auth_service()
        if epg_service is None:
            epg_service = cls.create_epg_service(auth_service)
        if cache_service is None:
            cache_service = cls.create_cache_service()
        if session_service is None:
            session_service = cls.create_session_service()

        # Načtení kvality z konfigurace, pokud není zadána
        if quality is None:
            # Vytvoření ConfigService pro načtení konfigurace
            config_service = cls.create_config_service()
            quality = config_service.get_value("QUALITY", "p5")

        # Vytvoření klíče pro instanci
        instance_key = f"catchup_{id(auth_service)}_{id(epg_service)}_{quality}"

        # Kontrola, zda instance již existuje
        if instance_key in cls._instances:
            return cls._instances[instance_key]

        # Vytvoření nové instance
        catchup_service = CatchupService(auth_service, epg_service, quality)
        cls._instances[instance_key] = catchup_service
        return catchup_service

    @classmethod
    def create_playlist_service(cls, channel_service=None, stream_service=None, cache_service=None):
        """
        Vytvoření instance PlaylistService

        Args:
            channel_service (ChannelService, optional): Instance služby pro kanály nebo None pro vytvoření nové
            stream_service (StreamService, optional): Instance služby pro streamy nebo None pro vytvoření nové
            cache_service (CacheService, optional): Instance služby pro cache

        Returns:
            PlaylistService: Instance služby pro playlisty
        """
        # Získání nebo vytvoření závislostí
        auth_service = None

        if channel_service is None:
            auth_service = cls.create_auth_service()
            channel_service = cls.create_channel_service(auth_service)

        if stream_service is None:
            if auth_service is None:
                auth_service = cls.create_auth_service()
            stream_service = cls.create_stream_service(auth_service)

        if cache_service is None:
            cache_service = cls.create_cache_service()

        # Vytvoření klíče pro instanci
        instance_key = f"playlist_{id(channel_service)}_{id(stream_service)}"

        # Kontrola, zda instance již existuje
        if instance_key in cls._instances:
            return cls._instances[instance_key]

        # Vytvoření nové instance
        playlist_service = PlaylistService(channel_service, stream_service)
        cls._instances[instance_key] = playlist_service
        return playlist_service

    @classmethod
    def create_client_service(cls, username=None, password=None, language=None,
                              quality=None, config_service=None):
        """
        Vytvoření instance ClientService

        Tato metoda vytvoří instanci ClientService a všechny potřebné závislosti.

        Args:
            username (str, optional): Přihlašovací jméno nebo None pro načtení z konfigurace
            password (str, optional): Heslo nebo None pro načtení z konfigurace
            language (str, optional): Kód jazyka (cz, sk) nebo None pro načtení z konfigurace
            quality (str, optional): Kvalita streamu (p1-p5) nebo None pro načtení z konfigurace
            config_service (ConfigService, optional): Instance služby pro konfiguraci

        Returns:
            ClientService: Instance klientské služby
        """
        # Načtení konfigurace
        if config_service is None:
            config_service = cls.create_config_service()

        if username is None:
            username = config_service.get_value("USERNAME", "")
        if password is None:
            password = config_service.get_value("PASSWORD", "")
        if language is None:
            language = config_service.get_value("LANGUAGE", "cz")
        if quality is None:
            quality = config_service.get_value("QUALITY", "p5")

        # Vytvoření klíče pro instanci
        instance_key = f"client_{username}_{language}_{quality}"

        # Kontrola, zda instance již existuje
        if instance_key in cls._instances:
            return cls._instances[instance_key]

        # Vytvoření nové instance
        client_service = ClientService(username, password, language, quality)
        cls._instances[instance_key] = client_service
        return client_service

    @classmethod
    def clear_instances(cls):
        """
        Vyčištění všech instancí
        """
        # Uzavření session služeb
        for instance in cls._instances.values():
            if hasattr(instance, 'close') and callable(instance.close):
                try:
                    instance.close()
                except Exception as e:
                    logger.warning(f"Chyba při uzavírání instance: {e}")

        # Vyčištění všech instancí
        cls._instances.clear()
        logger.debug("Všechny instance služeb byly vymazány")


# Funkce pro získání instance ClientService
def get_magenta_tv_service():
    """
    Získání instance klientské služby MagentaTV/MagioTV

    Returns:
        ClientService: Instance klientské služby
    """
    try:
        return ServiceFactory.create_client_service()
    except Exception as e:
        logger.error(f"Chyba při vytváření klientské služby: {e}")
        return None