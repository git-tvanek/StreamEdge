#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DeviceService - Služba pro správu zařízení MagentaTV/MagioTV
"""
import logging
from Models.device import Device
from Services.utils.constants import API_ENDPOINTS, TIME_CONSTANTS

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
        self.language = auth_service.language
        self.logger = logging.getLogger(f"{__name__}.device")

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
                f"{self.base_url}{API_ENDPOINTS['devices']['list']}",
                headers=headers,
                timeout=TIME_CONSTANTS["DEFAULT_TIMEOUT"]
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
            self.logger.error(f"Chyba při získání seznamu zařízení: {e}")
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
                f"{self.base_url}{API_ENDPOINTS['devices']['delete']}",
                params={"id": device_id},
                headers=headers,
                timeout=TIME_CONSTANTS["DEFAULT_TIMEOUT"]
            ).json()

            if response.get("success", False):
                self.logger.info(f"Zařízení s ID {device_id} bylo úspěšně odstraněno")
                return True
            else:
                self.logger.error(f"Chyba při odstraňování zařízení: {response.get('errorMessage', 'Neznámá chyba')}")
                return False

        except Exception as e:
            self.logger.error(f"Chyba při odstraňování zařízení: {e}")
            return False

    def get_current_device_info(self):
        """
        Získání informací o aktuálním zařízení

        Returns:
            dict: Informace o aktuálním zařízení nebo None při chybě
        """
        devices = self.get_devices()
        for device in devices:
            if device.get("is_this_device", False):
                return device
        return None

    def update_device_name(self, device_id, new_name):
        """
        Aktualizace názvu zařízení (pokud API podporuje tuto funkci)

        Args:
            device_id (str): ID zařízení
            new_name (str): Nový název zařízení

        Returns:
            bool: True pokud byla aktualizace úspěšná, jinak False
        """
        # Poznámka: Tato funkce je implementována jako příklad,
        # ale Magenta TV API nemusí podporovat přejmenování zařízení.
        # V takovém případě by bylo potřeba upravit implementaci podle
        # dostupného API.

        self.logger.warning("Přejmenování zařízení není momentálně podporováno API")
        return False

    def get_device_by_id(self, device_id):
        """
        Získání informací o konkrétním zařízení podle ID

        Args:
            device_id (str): ID zařízení

        Returns:
            dict: Informace o zařízení nebo None pokud zařízení nebylo nalezeno
        """
        devices = self.get_devices()
        for device in devices:
            if device.get("id") == device_id:
                return device
        return None

    def get_device_count(self):
        """
        Získání počtu registrovaných zařízení

        Returns:
            dict: Počet zařízení podle typu
        """
        devices = self.get_devices()
        if not devices:
            return {
                "total": 0,
                "mobile": 0,
                "stb": 0,
                "other": 0
            }

        # Rozdělení zařízení podle typu
        mobile_count = sum(1 for device in devices if device.get("type") == "mobile")
        stb_count = sum(1 for device in devices if device.get("type") == "stb")
        other_count = sum(1 for device in devices if device.get("type") not in ["mobile", "stb", "current"])

        return {
            "total": len(devices),
            "mobile": mobile_count,
            "stb": stb_count,
            "other": other_count
        }