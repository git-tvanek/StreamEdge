#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChannelService - Služba pro správu kanálů MagentaTV/MagioTV
"""
import logging
from Models.channel import Channel
from Services.utils.constants import API_ENDPOINTS, TIME_CONSTANTS

logger = logging.getLogger(__name__)


class ChannelService:
    """
    Služba pro získávání a správu kanálů
    """

    def __init__(self, auth_service):
        """
        Inicializace služby pro správu kanálů

        Args:
            auth_service (AuthService): Instance služby pro autentizaci
        """
        self.auth_service = auth_service
        self.session = auth_service.session
        self.base_url = auth_service.get_base_url()
        self.language = auth_service.language
        self.logger = logging.getLogger(f"{__name__}.channel")

    def _get_auth_headers(self):
        """
        Získání autorizačních hlaviček

        Returns:
            dict: Hlavičky s autorizačním tokenem nebo None při chybě
        """
        return self.auth_service.get_auth_headers()

    def get_channels(self):
        """
        Získání seznamu dostupných kanálů

        Returns:
            list: Seznam kanálů s jejich ID, názvem, logem a kategorií
        """
        # Získání autorizačních hlaviček
        headers = self._get_auth_headers()
        if not headers:
            return []

        try:
            # Získání kategorií pro kanály
            categories_response = self.session.get(
                f"{self.base_url}/home/categories",
                params={"language": self.language},
                headers=headers,
                timeout=TIME_CONSTANTS["DEFAULT_TIMEOUT"]
            ).json()

            categories = {}
            for category in categories_response.get("categories", []):
                for channel in category.get("channels", []):
                    categories[channel["channelId"]] = category["name"]

            # Získání seznamu kanálů
            params = {
                "list": "LIVE",
                "queryScope": "LIVE"
            }

            channels_response = self.session.get(
                f"{self.base_url}{API_ENDPOINTS['channels']['list']}",
                params=params,
                headers=headers,
                timeout=TIME_CONSTANTS["DEFAULT_TIMEOUT"]
            ).json()

            if not channels_response.get("success", True):
                self.logger.error("Chyba při získání kanálů")
                return []

            channels = []
            for item in channels_response.get("items", []):
                channel = item.get("channel", {})
                channel_id = channel.get("channelId")

                # Vytvoření objektu Channel
                channel_obj = Channel(
                    id=channel_id,
                    name=channel.get("name", ""),
                    original_name=channel.get("originalName", ""),
                    logo=channel.get("logoUrl", ""),
                    group=categories.get(channel_id, "Ostatní"),
                    has_archive=channel.get("hasArchive", False)
                )

                channels.append(channel_obj.to_dict())

            return channels

        except Exception as e:
            self.logger.error(f"Chyba při získání kanálů: {e}")
            return []

    def get_channel_by_id(self, channel_id):
        """
        Získání konkrétního kanálu podle ID

        Args:
            channel_id (str): ID kanálu

        Returns:
            dict: Informace o kanálu nebo None při chybě
        """
        # Získání seznamu všech kanálů
        channels = self.get_channels()

        # Vyhledání kanálu podle ID
        for channel in channels:
            if str(channel["id"]) == str(channel_id):
                return channel

        logger.warning(f"Kanál s ID {channel_id} nebyl nalezen")
        return None

    def get_channels_by_group(self, group_name):
        """
        Získání kanálů podle skupiny

        Args:
            group_name (str): Název skupiny

        Returns:
            list: Seznam kanálů v dané skupině
        """
        # Získání seznamu všech kanálů
        channels = self.get_channels()

        # Filtrování kanálů podle skupiny
        return [channel for channel in channels if channel["group"].lower() == group_name.lower()]

    def get_channel_groups(self):
        """
        Získání seznamu dostupných skupin kanálů

        Returns:
            list: Seznam názvů skupin
        """
        # Získání seznamu všech kanálů
        channels = self.get_channels()

        # Extrakce unikátních názvů skupin
        groups = set(channel["group"] for channel in channels)
        return sorted(list(groups))

    def search_channels(self, search_term):
        """
        Vyhledávání kanálů podle názvu

        Args:
            search_term (str): Hledaný výraz

        Returns:
            list: Seznam kanálů odpovídajících hledanému výrazu
        """
        if not search_term:
            return []

        # Získání seznamu všech kanálů
        channels = self.get_channels()
        search_term = search_term.lower()

        # Filtrování kanálů podle názvu
        return [
            channel for channel in channels
            if search_term in channel["name"].lower() or
               search_term in channel["original_name"].lower()
        ]