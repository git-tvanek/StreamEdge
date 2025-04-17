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

logger = logging.getLogger(__name__)


class ServiceFactory:
    """
    Továrna pro vytváření instancí služeb

    Tato třída zajišťuje vytváření instancí jednotlivých služeb
    s příslušnou konfigurací a zajišťuje jejich správné propojení.
    """

    _instances = {}

    @classmethod
    def create_auth_service(cls, username=None, password=None, language=None):
        """
        Vytvoření instance AuthService

        Args:
            username (str, optional): Přihlašovací jméno nebo None pro načtení z konfigurace
            password (str, optional): Heslo nebo None pro načtení z konfigurace
            language (str, optional): Kód jazyka (cz, sk) nebo None pro načtení z konfigurace

        Returns:
            AuthService: Instance služby pro autentizaci
        """
        # Načtení konfigurace, pokud nejsou parametry zadány
        if username is None:
            username = current_app.config.get("USERNAME", "")
        if password is None:
            password = current_app.config.get("PASSWORD", "")
        if language is None:
            language = current_app.config.get("LANGUAGE", "cz")

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
    def create_channel_service(cls, auth_service=None):
        """
        Vytvoření instance ChannelService

        Args:
            auth_service (AuthService, optional): Instance služby pro autentizaci nebo None pro vytvoření nové

        Returns:
            ChannelService: Instance služby pro kanály
        """
        # Získání nebo vytvoření AuthService
        if auth_service is None:
            auth_service = cls.create_auth_service()

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
    def create_stream_service(cls, auth_service=None, quality=None):
        """
        Vytvoření instance StreamService

        Args:
            auth_service (AuthService, optional): Instance služby pro autentizaci nebo None pro vytvoření nové
            quality (str, optional): Kvalita streamu (p1-p5) nebo None pro načtení z konfigurace

        Returns:
            StreamService: Instance služby pro streamy
        """
        # Získání nebo vytvoření AuthService
        if auth_service is None:
            auth_service = cls.create_auth_service()

        # Načtení konfigurace, pokud nejsou parametry zadány
        if quality is None:
            quality = current_app.config.get("QUALITY", "p5")

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
    def create_epg_service(cls, auth_service=None):
        """
        Vytvoření instance EPGService

        Args:
            auth_service (AuthService, optional): Instance služby pro autentizaci nebo None pro vytvoření nové

        Returns:
            EPGService: Instance služby pro EPG
        """
        # Získání nebo vytvoření AuthService
        if auth_service is None:
            auth_service = cls.create_auth_service()

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
    def create_device_service(cls, auth_service=None):
        """
        Vytvoření instance DeviceService

        Args:
            auth_service (AuthService, optional): Instance služby pro autentizaci nebo None pro vytvoření nové

        Returns:
            DeviceService: Instance služby pro zařízení
        """
        # Získání nebo vytvoření AuthService
        if auth_service is None:
            auth_service = cls.create_auth_service()

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
    def create_catchup_service(cls, auth_service=None, epg_service=None, quality=None):
        """
        Vytvoření instance CatchupService

        Args:
            auth_service (AuthService, optional): Instance služby pro autentizaci nebo None pro vytvoření nové
            epg_service (EPGService, optional): Instance služby pro EPG nebo None pro vytvoření nové
            quality (str, optional): Kvalita streamu (p1-p5) nebo None pro načtení z konfigurace

        Returns:
            CatchupService: Instance služby pro archiv
        """
        # Získání nebo vytvoření závislostí
        if auth_service is None:
            auth_service = cls.create_auth_service()
        if epg_service is None:
            epg_service = cls.create_epg_service(auth_service)
        if quality is None:
            quality = current_app.config.get("QUALITY", "p5")

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
    def create_playlist_service(cls, channel_service=None, stream_service=None):
        """
        Vytvoření instance PlaylistService

        Args:
            channel_service (ChannelService, optional): Instance služby pro kanály nebo None pro vytvoření nové
            stream_service (StreamService, optional): Instance služby pro streamy nebo None pro vytvoření nové

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
    def create_client_service(cls, username=None, password=None, language=None, quality=None):
        """
        Vytvoření instance ClientService

        Tato metoda vytvoří instanci ClientService a všechny potřebné závislosti.

        Args:
            username (str, optional): Přihlašovací jméno nebo None pro načtení z konfigurace
            password (str, optional): Heslo nebo None pro načtení z konfigurace
            language (str, optional): Kód jazyka (cz, sk) nebo None pro načtení z konfigurace
            quality (str, optional): Kvalita streamu (p1-p5) nebo None pro načtení z konfigurace

        Returns:
            ClientService: Instance klientské služby
        """
        # Načtení konfigurace, pokud nejsou parametry zadány
        if username is None:
            username = current_app.config.get("USERNAME", "")
        if password is None:
            password = current_app.config.get("PASSWORD", "")
        if language is None:
            language = current_app.config.get("LANGUAGE", "cz")
        if quality is None:
            quality = current_app.config.get("QUALITY", "p5")

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