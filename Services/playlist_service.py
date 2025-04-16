#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PlaylistService - Služba pro generování M3U playlistů z MagentaTV/MagioTV
"""
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

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
        self.logger = logging.getLogger(f"{__name__}.playlist")

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

    def generate_epg_xml(self, server_url="", days=3, epg_service=None):
        """
        Vygenerování XML pro EPG (Electronic Program Guide)

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

        try:
            # Získání seznamu kanálů
            channels = self.channel_service.get_channels()
            if not channels:
                return ""

            # Získání EPG dat
            all_epg = epg_service.get_epg(days_back=0, days_forward=days)
            if not all_epg:
                return ""

            # Vytvoření kořenového elementu XML
            root = ET.Element("tv")
            root.set("generator-info-name", "StreamEdge")
            root.set("generator-info-url", server_url)

            # Přidání informací o kanálech
            for channel in channels:
                channel_id = str(channel["id"])
                channel_element = ET.SubElement(root, "channel")
                channel_element.set("id", channel_id)

                # Přidání jména kanálu
                display_name = ET.SubElement(channel_element, "display-name")
                display_name.text = channel["name"]

                # Přidání ikony kanálu
                if channel.get("logo"):
                    icon = ET.SubElement(channel_element, "icon")
                    icon.set("src", channel["logo"])

            # Přidání programů pro každý kanál
            for channel_id, programs in all_epg.items():
                for program in programs:
                    # Vytvoření elementu programu
                    prog_element = ET.SubElement(root, "programme")
                    prog_element.set("channel", str(channel_id))

                    # Formátování začátku a konce
                    start = datetime.strptime(program["start_time"], "%Y-%m-%d %H:%M:%S")
                    end = datetime.strptime(program["end_time"], "%Y-%m-%d %H:%M:%S")

                    prog_element.set("start", start.strftime("%Y%m%d%H%M%S %z"))
                    prog_element.set("stop", end.strftime("%Y%m%d%H%M%S %z"))

                    # Přidání názvu
                    title = ET.SubElement(prog_element, "title")
                    title.text = program["title"]

                    # Přidání popisu
                    if program.get("description"):
                        desc = ET.SubElement(prog_element, "desc")
                        desc.text = program["description"]

                    # Přidání kategorie
                    if program.get("category"):
                        category = ET.SubElement(prog_element, "category")
                        category.text = program["category"]

                    # Přidání roku
                    if program.get("year"):
                        date = ET.SubElement(prog_element, "date")
                        date.text = str(program["year"])

                    # Přidání délky trvání
                    if program.get("duration"):
                        length = ET.SubElement(prog_element, "length")
                        length.set("units", "seconds")
                        length.text = str(program["duration"])

                    # Přidání obrázků
                    for image_url in program.get("images", []):
                        icon = ET.SubElement(prog_element, "icon")
                        icon.set("src", image_url)

            # Konverze XML na řetězec
            from xml.dom import minidom
            xml_str = minidom.parseString(ET.tostring(root, 'utf-8')).toprettyxml(indent="  ")
            return xml_str

        except Exception as e:
            self.logger.error(f"Chyba při generování EPG XML: {e}")
            return ""

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