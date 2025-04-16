#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DeviceService - Služba pro správu zařízení MagentaTV/MagioTV
"""
import logging
from app.models.device import Device

logger = logging.getLogger(__name__)


class DeviceService:
    """
    Služba pro správu zařízení
    """

    def __init__(self, auth_service):
        """
        Inicializace služby pro správu zařízení

        Args:
            auth_service (AuthService): Instance služby pro autentizaci
        """
        self.auth_service = auth_service
        self.session = auth_service.session
        self.base_url = auth_service.get_base_url()

    def get_devices(self):
        """
        Získání seznamu registrovaných zařízení

        Returns:
            list: Seznam zařízení s jejich ID a názvy
        """
        # Získání autorizačních hlaviček
        headers = self.auth_service.get_auth_headers()
        if not headers:
            return []

        try:
            response = self.session.get(
                f"{self.base_url}/v2/home/my-devices",
                headers=headers,
                timeout=30
            ).json()

            devices = []

            # Aktuální zařízení
            if "thisDevice" in response:
                device = Device(
                    id=response["thisDevice"]["id"],
                    name=response["thisDevice"]["name"],
                    type="current",
                    is_this_device=True
                )
                devices.append(device.to_dict())

            # Mobilní zařízení
            for device_data in response.get("smallScreenDevices", []):
                device = Device(
                    id=device_data["id"],
                    name=device_data["name"],
                    type="mobile",
                    is_this_device=False
                )
                devices.append(device.to_dict())

            # STB a TV zařízení
            for device_data in response.get("stbAndBigScreenDevices", []):
                device = Device(
                    id=device_data["id"],
                    name=device_data["name"],
                    type="stb",
                    is_this_device=False
                )
                devices.append(device.to_dict())

            return devices

        except Exception as e:
            logger.error(f"Chyba při získání seznamu zařízení: {e}")
            return []

    def delete_device(self, device_id):
        """
        Odstranění zařízení podle ID

        Args:
            device_id (str): ID zařízení

        Returns:
            bool: True v případě úspěšného odstranění, jinak False
        """
        # Získání autorizačních hlaviček
        headers = self.auth_service.get_auth_headers()
        if not headers:
            return False

        try:
            response = self.session.get(
                f"{self.base_url}/home/deleteDevice",
                params={"id": device_id},
                headers=headers,
                timeout=30
            ).json()

            if response.get("success", False):
                logger.info(f"Zařízení s ID {device_id} bylo úspěšně odstraněno")
                return True
            else:
                logger.error(f"Chyba při odstraňování zařízení: {response.get('errorMessage', 'Neznámá chyba')}")
                return False

        except Exception as e:
            logger.error(f"Chyba při odstraňování zařízení: {e}")
            return False