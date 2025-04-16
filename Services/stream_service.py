#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
StreamService - Služba pro získávání streamů z MagentaTV/MagioTV
"""
import logging
from urllib.parse import urlparse
from app.models.stream import Stream

logger = logging.getLogger(__name__)


class StreamService:
    """
    Služba pro získávání streamů živého vysílání
    """

    def __init__(self, auth_service, quality="p5"):
        """
        Inicializace služby pro získávání streamů

        Args:
            auth_service (AuthService): Instance služby pro autentizaci
            quality (str): Kvalita streamu (p1-p5, kde p5 je nejvyšší)
        """
        self.auth_service = auth_service
        self.session = auth_service.session
        self.base_url = auth_service.get_base_url()
        self.language = auth_service.language
        self.quality = quality
        self.device_name = auth_service.device_name
        self.device_type = auth_service.device_type

    def get_live_stream(self, channel_id):
        """
        Získání URL pro streamování živého vysílání kanálu

        Args:
            channel_id (int): ID kanálu

        Returns:
            dict: Informace o streamu včetně URL nebo None v případě chyby
        """
        # Získání autorizačních hlaviček
        headers = self.auth_service.get_auth_headers()
        if not headers:
            return None

        params = {
            "service": "LIVE",
            "name": self.device_name,
            "devtype": self.device_type,
            "id": int(channel_id),
            "prof": self.quality,
            "ecid": "",
            "drm": "widevine",
            "start": "LIVE",
            "end": "END",
            "device": "OTT_PC_HD_1080p_v2"
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
                timeout=10
            ).json()

            if not response.get("success", False):
                error_msg = response.get('errorMessage', 'Neznámá chyba')
                logger.error(f"Chyba při získání stream URL: {error_msg}")
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
                timeout=10
            )

            final_url = redirect_response.headers.get("location", url)

            # Vytvoření objektu Stream
            stream = Stream(
                url=final_url,
                headers=dict(headers_redirect),
                content_type=redirect_response.headers.get("Content-Type", "application/vnd.apple.mpegurl"),
                is_live=True
            )

            return stream.to_dict()

        except Exception as e:
            logger.error(f"Chyba při získání stream URL: {e}")
            return None