#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChannelService - Služba pro správu kanálů MagentaTV/MagioTV
"""
import logging
from Models.channel import Channel
from Services.base.authenticated_service_base import AuthenticatedServiceBase
from Services.utils.constants import API_ENDPOINTS, TIME_CONSTANTS

logger = logging.getLogger(__name__)


class ChannelService(AuthenticatedServiceBase):
    """
    Služba pro získávání a správu kanálů
    """

    def __init__(self, auth_service, cache_service=None, system_service=None,
                 config_service=None, session_service=None):
        """
        Inicializace služby pro správu kanálů

        Args:
            auth_service (AuthService): Instance služby pro autentizaci
            cache_service (CacheService, optional): Instance služby pro cache
            system_service (SystemService, optional): Instance služby pro monitoring
            config_service (ConfigService, optional): Instance služby pro konfiguraci
            session_service (SessionService, optional): Instance služby pro HTTP komunikaci
        """
        super().__init__("channel", auth_service)

        # Uložení závislostí na pomocné služby
        self.cache_service = cache_service
        self.system_service = system_service
        self.config_service = config_service
        self.session_service = session_service

        # Vytvořit HTTP session z SessionService nebo použít tu z AuthService
        if self.session_service:
            self.session = self.session_service.session
        else:
            self.session = auth_service.session

        self.base_url = auth_service.get_base_url()
        self.language = auth_service.language

        # Konfigurace z ConfigService
        self.cache_timeout = self._get_cache_timeout()

        # Zaznamenání inicializace v SystemService
        if self.system_service:
            self.system_service.log_event(
                "channel", "init",
                f"ChannelService inicializována (jazyk: {self.language})"
            )

    def _get_cache_timeout(self):
        """
        Získání timeout hodnoty pro cache kanálů

        Returns:
            int: Timeout v sekundách
        """
        default_timeout = TIME_CONSTANTS.get("DEFAULT_TIMEOUT", 3600)

        if self.config_service:
            return self.config_service.get_value("CHANNELS_CACHE_TIMEOUT", default_timeout)

        return default_timeout

    def get_channels(self):
        """
        Získání seznamu dostupných kanálů

        Returns:
            list: Seznam kanálů s jejich ID, názvem, logem a kategorií
        """
        # Pokus o získání z cache, pokud je k dispozici
        if self.cache_service:
            channels = self.cache_service.get_from_cache(
                f"channels_{self.language}",
                self._fetch_channels
            )
            if channels:
                if self.system_service:
                    self.system_service.log_event(
                        "channel", "cache_hit",
                        f"Kanály byly načteny z cache (počet: {len(channels)})"
                    )
                return channels

        # Pokud není cache nebo v cache nejsou data, získáme je přímo
        return self._fetch_channels()

    def _fetch_channels(self):
        """
        Interní metoda pro načtení kanálů přímo z API

        Returns:
            list: Seznam kanálů
        """
        # Získání autorizačních hlaviček
        headers = self._get_auth_headers()
        if not headers:
            if self.system_service:
                self.system_service.log_error(
                    "channel", "Nelze získat autorizační hlavičky"
                )
            return []

        try:
            # Získání kategorií pro kanály
            if self.session_service:
                categories_response = self.session_service.get_json(
                    f"{self.base_url}/home/categories",
                    params={"language": self.language},
                    headers=headers
                )
            else:
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

            if self.session_service:
                channels_response = self.session_service.get_json(
                    f"{self.base_url}{API_ENDPOINTS['channels']['list']}",
                    params=params,
                    headers=headers
                )
            else:
                channels_response = self.session.get(
                    f"{self.base_url}{API_ENDPOINTS['channels']['list']}",
                    params=params,
                    headers=headers,
                    timeout=TIME_CONSTANTS["DEFAULT_TIMEOUT"]
                ).json()

            if not channels_response.get("success", True):
                error_msg = channels_response.get('errorMessage', 'Neznámá chyba')
                self.logger.error(f"Chyba při získání kanálů: {error_msg}")
                if self.system_service:
                    self.system_service.log_error(
                        "channel", f"Chyba při získání kanálů: {error_msg}"
                    )
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

            # Uložení výsledku do cache
            if self.cache_service and channels:
                self.cache_service.store_in_cache(
                    f"channels_{self.language}",
                    channels,
                    cache_timeout=self.cache_timeout
                )
                if self.system_service:
                    self.system_service.log_event(
                        "channel", "cache_update",
                        f"Kanály byly uloženy do cache (počet: {len(channels)})"
                    )

            return channels

        except Exception as e:
            error_msg = f"Chyba při získání kanálů: {e}"
            self.logger.error(error_msg)
            if self.system_service:
                self.system_service.log_error("channel", error_msg)
            return []

    def get_channel_by_id(self, channel_id):
        """
        Získání konkrétního kanálu podle ID

        Args:
            channel_id (str): ID kanálu

        Returns:
            dict: Informace o kanálu nebo None při chybě
        """
        # Pokus o získání z cache, pokud je k dispozici
        if self.cache_service:
            channel_key = f"channel_{self.language}_{channel_id}"
            channel = self.cache_service.get_from_cache(
                channel_key,
                self._fetch_channel_by_id,
                channel_id
            )
            if channel:
                return channel

        return self._fetch_channel_by_id(channel_id)

    def _fetch_channel_by_id(self, channel_id):
        """
        Interní metoda pro načtení konkrétního kanálu

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
                # Uložení výsledku do cache
                if self.cache_service:
                    channel_key = f"channel_{self.language}_{channel_id}"
                    self.cache_service.store_in_cache(
                        channel_key,
                        channel,
                        cache_timeout=self.cache_timeout
                    )
                return channel

        if self.system_service:
            self.system_service.log_event(
                "channel", "not_found",
                f"Kanál s ID {channel_id} nebyl nalezen"
            )
        self.logger.warning(f"Kanál s ID {channel_id} nebyl nalezen")
        return None

    def get_channels_by_group(self, group_name):
        """
        Získání kanálů podle skupiny

        Args:
            group_name (str): Název skupiny

        Returns:
            list: Seznam kanálů v dané skupině
        """
        # Pokus o získání z cache, pokud je k dispozici
        if self.cache_service:
            group_key = f"channels_group_{self.language}_{group_name.lower()}"
            group_channels = self.cache_service.get_from_cache(
                group_key,
                self._fetch_channels_by_group,
                group_name
            )
            if group_channels is not None:
                return group_channels

        return self._fetch_channels_by_group(group_name)

    def _fetch_channels_by_group(self, group_name):
        """
        Interní metoda pro načtení kanálů podle skupiny

        Args:
            group_name (str): Název skupiny

        Returns:
            list: Seznam kanálů v dané skupině
        """
        # Získání seznamu všech kanálů
        channels = self.get_channels()

        # Filtrování kanálů podle skupiny
        group_channels = [
            channel for channel in channels
            if channel["group"].lower() == group_name.lower()
        ]

        # Uložení výsledku do cache
        if self.cache_service:
            group_key = f"channels_group_{self.language}_{group_name.lower()}"
            self.cache_service.store_in_cache(
                group_key,
                group_channels,
                cache_timeout=self.cache_timeout
            )
            if self.system_service:
                self.system_service.log_event(
                    "channel", "group_cache",
                    f"Kanály pro skupinu {group_name} uloženy do cache (počet: {len(group_channels)})"
                )

        return group_channels

    def get_channel_groups(self):
        """
        Získání seznamu dostupných skupin kanálů

        Returns:
            list: Seznam názvů skupin
        """
        # Pokus o získání z cache, pokud je k dispozici
        if self.cache_service:
            groups_key = f"channel_groups_{self.language}"
            groups = self.cache_service.get_from_cache(
                groups_key,
                self._fetch_channel_groups
            )
            if groups is not None:
                return groups

        return self._fetch_channel_groups()

    def _fetch_channel_groups(self):
        """
        Interní metoda pro načtení skupin kanálů

        Returns:
            list: Seznam názvů skupin
        """
        # Získání seznamu všech kanálů
        channels = self.get_channels()

        # Extrakce unikátních názvů skupin
        groups = set(channel["group"] for channel in channels)
        group_list = sorted(list(groups))

        # Uložení výsledku do cache
        if self.cache_service:
            groups_key = f"channel_groups_{self.language}"
            self.cache_service.store_in_cache(
                groups_key,
                group_list,
                cache_timeout=self.cache_timeout
            )
            if self.system_service:
                self.system_service.log_event(
                    "channel", "groups_cache",
                    f"Seznam skupin kanálů uložen do cache (počet: {len(group_list)})"
                )

        return group_list

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

        # U vyhledávání nemá smysl používat cache, protože se hledané výrazy mohou
        # velmi lišit, ale můžeme cachovat seznam kanálů, ve kterém vyhledáváme

        # Získání seznamu všech kanálů
        channels = self.get_channels()
        search_term = search_term.lower()

        # Filtrování kanálů podle názvu
        search_results = [
            channel for channel in channels
            if search_term in channel["name"].lower() or
               search_term in channel["original_name"].lower()
        ]

        if self.system_service:
            self.system_service.log_event(
                "channel", "search",
                f"Vyhledávání kanálů pro výraz '{search_term}' (nalezeno: {len(search_results)})"
            )

        return search_results

    def clear_cache(self):
        """
        Vyčištění cache pro kanály

        Returns:
            bool: True pokud bylo čištění úspěšné
        """
        if not self.cache_service:
            return False

        try:
            # Vyčištění všech cache záznamů souvisejících s kanály
            self.cache_service.clear_cache(f"channels_{self.language}")
            self.cache_service.clear_cache(f"channel_groups_{self.language}")

            # Vyčištění cache pro jednotlivé kanály podle ID
            # (použití wildcard pro všechny záznamy začínající prefixem)
            self.cache_service.clear_cache(f"channel_{self.language}_*")
            self.cache_service.clear_cache(f"channels_group_{self.language}_*")

            if self.system_service:
                self.system_service.log_event(
                    "channel", "cache_clear",
                    "Cache kanálů byla vyčištěna"
                )

            return True

        except Exception as e:
            error_msg = f"Chyba při čištění cache kanálů: {e}"
            self.logger.error(error_msg)
            if self.system_service:
                self.system_service.log_error("channel", error_msg)
            return False