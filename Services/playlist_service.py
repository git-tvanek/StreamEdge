#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PlaylistService - Služba pro generování M3U playlistů z MagentaTV/MagioTV
"""
import logging

logger = logging.getLogger(__name__)


class PlaylistService:
    """
    Služba pro generování M3U playlistů
    """

    def __init__(self, channel_service, stream_service):
        """
        Inicializace služby pro generování playlistů

        Args:
            channel_service (ChannelService): Instance služby pro správu kanálů
            stream_service (StreamService): Instance služby pro streamy
        """
        self.channel_service = channel_service
        self.stream_service = stream_service

    def generate_m3u_playlist(self, server_url=""):
        """
        Vygenerování M3U playlistu pro použití v IPTV přehrávačích

        Args:
            server_url (str): URL serveru pro přesměrování

        Returns:
            str: Obsah M3U playlistu
        """
        channels = self.channel_service.get_channels()
        if not channels:
            return ""

        playlist = "#EXTM3U\n"

        for channel in channels:
            channel_id = channel["id"]
            name = channel["name"].replace(" HD", "")
            group = channel["group"]
            logo = channel["logo"]
            has_archive = channel["has_archive"]

            # Zápis informací o kanálu
            playlist += f'#EXTINF:-1 tvg-id="{channel_id}" tvg-name="{name}" group-title="{group}"'

            # Přidání informací o archivu, pokud je dostupný
            if has_archive and server_url:
                playlist += f' catchup="default" catchup-source="{server_url}/api/catchup/{channel_id}/' + '${start}-${end}' + '" catchup-days="7"'

            # Přidání loga, pokud je dostupné
            if logo:
                playlist += f' tvg-logo="{logo}"'

            playlist += f',{name}\n'

            # URL pro streamování
            if server_url:
                playlist += f'{server_url}/api/stream/{channel_id}?redirect=1\n'
            else:
                stream_info = self.stream_service.get_live_stream(channel_id)
                if stream_info:
                    playlist += f'{stream_info["url"]}\n'
                else:
                    playlist += f'http://127.0.0.1/error.m3u8\n'

        return playlist

    def generate_epg_xml(self, server_url="", days=3):
        """
        Vygenerování XML pro EPG (Electronic Program Guide)

        Args:
            server_url (str): URL serveru
            days (int): Počet dní pro EPG

        Returns:
            str: XML data pro EPG nebo prázdný řetězec při chybě
        """
        # Tato funkce je zatím jen návrh - implementace by vyžadovala
        # další práci, protože je potřeba generovat XML v XMLTV formátu
        # a získat EPG data pro všechny kanály
        #
        # Jelikož je tato funkce mimo základní požadavky, ponecháme ji
        # jako budoucí rozšíření

        logger.warning("Generování EPG XML zatím není implementováno")
        return ""