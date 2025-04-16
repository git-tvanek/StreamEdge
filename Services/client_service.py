#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ClientService - Hlavní klientská služba pro MagentaTV/MagioTV API
"""
import logging
import time
from flask import current_app
from Services.auth_service import AuthService
from Services.channel_service import ChannelService
from Services.stream_service import StreamService
from Services.epg_service import EPGService
from Services.device_service import DeviceService
from Services.playlist_service import PlaylistService
from Services.catchup_service import CatchupService

logger = logging.getLogger(__name__)


class ClientService:
    """
    Hlavní klientská služba pro MagentaTV/MagioTV API

    Tato služba používá ostatní specializované služby pro poskytování
    kompletního API rozhraní pro aplikaci.
    """

    def __init__(self, username=None, password=None, language=None, quality=None):
        """
        Inicializace klientské služby

        Args:
            username (str, optional): Přihlašovací jméno nebo None pro načtení z konfigurace
            password (str, optional): Heslo nebo None pro načtení z konfigurace
            language (str, optional): Kód jazyka (cz, sk) nebo None pro načtení z konfigurace
            quality (str, optional): Kvalita streamu (p1-p5) nebo None pro načtení z konfigurace
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

        # Inicializace služeb
        self.auth_service = AuthService(username, password, language)
        self.channel_service = ChannelService(self.auth_service)
        self.stream_service = StreamService(self.auth_service, quality)
        self.epg_service = EPGService(self.auth_service)
        self.device_service = DeviceService(self.auth_service)
        self.catchup_service = CatchupService(self.auth_service, self.epg_service, quality)
        self.playlist_service = PlaylistService(self.channel_service, self.stream_service)

        # Základní údaje
        self.language = language
        self.quality = quality

    def login(self):
        """
        Přihlášení k službě

        Returns:
            bool: True pokud bylo přihlášení úspěšné
        """
        return self.auth_service.login()

    def check_login(self):
        """
        Kontrola přihlášení

        Returns:
            bool: True pokud je klient přihlášen
        """
        return self.auth_service.refresh_access_token()

    def logout(self):
        """
        Odhlášení a vymazání tokenů

        Returns:
            bool: True pokud bylo odhlášení úspěšné
        """
        return self.auth_service.logout()

    def get_status(self):
        """
        Získání stavu připojení a základních informací

        Returns:
            dict: Stav připojení a základní informace
        """
        auth_headers = self.auth_service.get_auth_headers()
        token_valid = auth_headers is not None

        return {
            "status": "online" if token_valid else "offline",
            "language": self.language,
            "quality": self.quality,
            "refresh_token_valid": bool(self.auth_service.refresh_token),
            "token_expires": int(self.auth_service.token_expires - time.time()) if token_valid else 0
        }

    # === Rozhraní kanálů ===

    def get_channels(self):
        """
        Získání seznamu kanálů

        Returns:
            list: Seznam kanálů
        """
        return self.channel_service.get_channels()

    def get_channel(self, channel_id):
        """
        Získání konkrétního kanálu

        Args:
            channel_id (str): ID kanálu

        Returns:
            dict: Informace o kanálu nebo None
        """
        return self.channel_service.get_channel_by_id(channel_id)

    def get_channel_groups(self):
        """
        Získání seznamu skupin kanálů

        Returns:
            list: Seznam názvů skupin
        """
        return self.channel_service.get_channel_groups()

    # === Rozhraní streamů ===

    def get_live_stream_url(self, channel_id):
        """
        Získání URL pro živé vysílání

        Args:
            channel_id (str): ID kanálu

        Returns:
            dict: Informace o streamu včetně URL nebo None
        """
        return self.stream_service.get_live_stream(channel_id)

    def get_catchup_stream_by_id(self, schedule_id):
        """
        Získání URL pro přehrávání archivu podle ID pořadu

        Args:
            schedule_id (str): ID pořadu v programu

        Returns:
            dict: Informace o streamu včetně URL nebo None
        """
        return self.catchup_service.get_catchup_stream_by_id(schedule_id)

    def get_catchup_by_time(self, channel_id, start_timestamp, end_timestamp):
        """
        Získání URL pro přehrávání archivu podle času

        Args:
            channel_id (str): ID kanálu
            start_timestamp (int): Čas začátku v Unix timestamp
            end_timestamp (int): Čas konce v Unix timestamp

        Returns:
            dict: Informace o streamu včetně URL nebo None
        """
        return self.catchup_service.get_catchup_by_time(channel_id, start_timestamp, end_timestamp)

    def get_catchup_availability(self, channel_id):
        """
        Zjištění dostupnosti archivu pro daný kanál

        Args:
            channel_id (str): ID kanálu

        Returns:
            dict: Informace o dostupnosti archivu
        """
        return self.catchup_service.get_catchup_availability(channel_id)

    # === Rozhraní EPG ===

    def get_epg(self, channel_id=None, days_back=1, days_forward=1):
        """
        Získání programových dat

        Args:
            channel_id (str, optional): ID kanálu nebo None pro všechny kanály
            days_back (int): Počet dní zpět
            days_forward (int): Počet dní dopředu

        Returns:
            dict: EPG data rozdělená podle kanálů nebo None
        """
        return self.epg_service.get_epg(channel_id, days_back, days_forward)

    # === Rozhraní zařízení ===

    def get_devices(self):
        """
        Získání seznamu zařízení

        Returns:
            list: Seznam zařízení
        """
        return self.device_service.get_devices()

    def delete_device(self, device_id):
        """
        Odstranění zařízení

        Args:
            device_id (str): ID zařízení

        Returns:
            bool: True v případě úspěšného odstranění
        """
        return self.device_service.delete_device(device_id)

    # === Rozhraní playlistů ===

    def generate_m3u_playlist(self, server_url=""):
        """
        Vygenerování M3U playlistu

        Args:
            server_url (str): URL serveru pro přesměrování

        Returns:
            str: Obsah M3U playlistu
        """
        return self.playlist_service.generate_m3u_playlist(server_url)