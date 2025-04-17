#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CatchupService - Služba pro správu archivu/catchup funkcí MagentaTV/MagioTV
"""
import logging
from datetime import datetime, timedelta
from urllib.parse import urlparse
from Services.base.authenticated_service_base import AuthenticatedServiceBase
from Services.utils.constants import TIME_CONSTANTS
from Models.stream import Stream

logger = logging.getLogger(__name__)


class CatchupService(AuthenticatedServiceBase):
    """
    Služba pro získávání streamů z archivu/catchup
    """

    def __init__(self, auth_service, epg_service, quality="p5"):
        """
        Inicializace služby pro archiv

        Args:
            auth_service (AuthService): Instance služby pro autentizaci
            epg_service (EPGService): Instance služby pro EPG
            quality (str): Kvalita streamu (p1-p5, kde p5 je nejvyšší)
        """
        super().__init__("catchup", auth_service)
        self.epg_service = epg_service
        self.session = auth_service.session
        self.base_url = auth_service.get_base_url()
        self.language = auth_service.language
        self.quality = quality
        self.device_name = auth_service.device_name
        self.device_type = auth_service.device_type

    def get_catchup_stream_by_id(self, schedule_id):
        """
        Získání URL pro přehrávání archivu podle ID pořadu

        Args:
            schedule_id (int): ID pořadu v programu

        Returns:
            dict: Informace o streamu včetně URL nebo None v případě chyby
        """
        # Získání autorizačních hlaviček
        headers = self._get_auth_headers()
        if not headers:
            return None

        params = {
            "service": "ARCHIVE",
            "name": self.device_name,
            "devtype": self.device_type,
            "id": int(schedule_id),
            "prof": self.quality,
            "ecid": "",
            "drm": "widevine"
        }

        stream_headers = {
            **headers,
            "Accept": "*/*",
            "Referer": f"https://{self.language}go.magio.tv/"
        }

        try:
            response = self.session.get(
                f"{self.base_url}/v2/television/stream-url",
                params=params,
                headers=stream_headers,
                timeout=TIME_CONSTANTS["STREAM_TIMEOUT"]
            ).json()

            if not response.get("success", False):
                error_msg = response.get('errorMessage', 'Neznámá chyba')
                self.logger.error(f"Chyba při získání catchup URL: {error_msg}")
                return None

            url = response["url"]

            # Následování přesměrování pro získání skutečné URL
            headers_redirect = {
                "Host": urlparse(url).netloc,
                "User-Agent": self.auth_service.user_agent,
                "Authorization": f"Bearer {self.auth_service.access_token}",
                "Accept": "*/*",
                "Referer": f"https://{self.language}go.magio.tv/"
            }

            redirect_response = self.session.get(
                url,
                headers=headers_redirect,
                allow_redirects=False,
                timeout=TIME_CONSTANTS["STREAM_TIMEOUT"]
            )

            final_url = redirect_response.headers.get("location", url)

            # Vytvoření objektu Stream
            stream = Stream(
                url=final_url,
                headers=dict(headers_redirect),
                content_type=redirect_response.headers.get("Content-Type", "application/vnd.apple.mpegurl"),
                is_live=False
            )

            return stream.to_dict()

        except Exception as e:
            self.logger.error(f"Chyba při získání catchup URL: {e}")
            return None

    def get_catchup_by_time(self, channel_id, start_timestamp, end_timestamp):
        """
        Získání URL pro přehrávání archivu podle času začátku a konce

        Args:
            channel_id (int): ID kanálu
            start_timestamp (int): Čas začátku v Unix timestamp
            end_timestamp (int): Čas konce v Unix timestamp

        Returns:
            dict: Informace o streamu včetně URL nebo None v případě chyby
        """
        # Nejprve najdeme program podle času
        program_info = self.epg_service.find_program_by_time(channel_id, start_timestamp, end_timestamp)
        if not program_info or not program_info.get("schedule_id"):
            self.logger.error("Pořad nebyl nalezen v EPG")
            return None

        # Použijeme ID pořadu pro získání streamu
        schedule_id = program_info["schedule_id"]
        return self.get_catchup_stream_by_id(schedule_id)

    def get_catchup_availability(self, channel_id):
        """
        Zjištění dostupnosti archivu pro daný kanál

        Args:
            channel_id (int): ID kanálu

        Returns:
            dict: Informace o dostupnosti archivu nebo None při chybě
        """
        # Získání dat z EPG pro poslední týden
        epg_data = self.epg_service.get_epg(channel_id, days_back=7, days_forward=0)

        if not epg_data or not epg_data.get(channel_id):
            return {
                "has_archive": False,
                "days_available": 0,
                "programs_count": 0
            }

        # Počet programů v archivu
        programs_count = len(epg_data[channel_id])

        # Zjištění nejstaršího dostupného programu
        oldest_timestamp = None
        now = datetime.now().timestamp()

        for program in epg_data[channel_id]:
            program_start = datetime.strptime(program["start_time"], "%Y-%m-%d %H:%M:%S").timestamp()
            if oldest_timestamp is None or program_start < oldest_timestamp:
                oldest_timestamp = program_start

        # Výpočet počtu dní v archivu
        days_available = (now - oldest_timestamp) / (24 * 3600) if oldest_timestamp else 0

        return {
            "has_archive": programs_count > 0,
            "days_available": round(days_available, 1),
            "programs_count": programs_count
        }

    def get_program_catchup(self, program_id):
        """
        Získání streamu pro konkrétní program

        Args:
            program_id (int): ID programu v EPG

        Returns:
            dict: Informace o streamu nebo None při chybě
        """
        return self.get_catchup_stream_by_id(program_id)

    def get_timeshift_window(self, channel_id):
        """
        Získání časového okna pro timeshift (posun času) kanálu

        Args:
            channel_id (int): ID kanálu

        Returns:
            dict: Informace o dostupném časovém okně pro timeshift
        """
        # Získání dat dostupnosti archivu
        availability = self.get_catchup_availability(channel_id)

        now = datetime.now()
        if not availability or not availability.get("has_archive", False):
            return {
                "start_time": now.timestamp(),
                "end_time": now.timestamp(),
                "duration_hours": 0,
                "available": False
            }

        # Výpočet časového okna
        days_available = availability.get("days_available", 0)
        start_time = now - timedelta(days=days_available)

        return {
            "start_time": start_time.timestamp(),
            "end_time": now.timestamp(),
            "duration_hours": days_available * 24,
            "available": True
        }