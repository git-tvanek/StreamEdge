#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PlaylistService - Služba pro generování M3U playlistů z MagentaTV/MagioTV
"""
import logging
from Services.base.service_base import ServiceBase

logger = logging.getLogger(__name__)


class PlaylistService(ServiceBase):
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
        super().__init__("playlist")
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

    def get_epg_xml(self, server_url="", days=3, epg_service=None):
        """
        Získání XML dat pro EPG (Electronic Program Guide) s využitím EPGService

        Tato metoda je wrapper kolem EPGService.export_epg_to_xml pro zachování
        zpětné kompatibility a jednodušší přístup k EPG datům.

        Args:
            server_url (str): URL serveru
            days (int): Počet dní pro EPG
            epg_service (EPGService): Instance služby pro EPG

        Returns:
            str: XML data pro EPG nebo prázdný řetězec při chybě
        """
        if not epg_service:
            self.logger.error("EPG služba není k dispozici")
            return ""

        return epg_service.export_epg_to_xml(server_url, days, self.channel_service)

    def generate_simple_m3u(self, server_url=""):
        """
        Vygenerování jednoduchého M3U playlistu bez dodatečných metadat

        Args:
            server_url (str): URL serveru pro přesměrování

        Returns:
            str: Obsah jednoduchého M3U playlistu
        """
        channels = self.channel_service.get_channels()
        if not channels:
            return ""

        playlist = "#EXTM3U\n"

        for channel in channels:
            channel_id = channel["id"]
            name = channel["name"]

            # Základní zápis informací o kanálu
            playlist += f'#EXTINF:-1,{name}\n'

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

    def generate_by_groups(self, server_url=""):
        """
        Vygenerování M3U playlistu rozděleného podle skupin kanálů

        Args:
            server_url (str): URL serveru pro přesměrování

        Returns:
            dict: Slovník s playlistem pro každou skupinu
        """
        channels = self.channel_service.get_channels()
        if not channels:
            return {}

        # Rozdělení kanálů podle skupin
        groups = {}
        for channel in channels:
            group = channel["group"]
            if group not in groups:
                groups[group] = []
            groups[group].append(channel)

        # Generování playlistu pro každou skupinu
        playlists = {}
        for group, group_channels in groups.items():
            playlist = "#EXTM3U\n"

            for channel in group_channels:
                channel_id = channel["id"]
                name = channel["name"].replace(" HD", "")
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

            playlists[group] = playlist

        return playlists