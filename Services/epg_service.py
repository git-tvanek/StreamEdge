#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EPGService - Služba pro získávání programových dat (EPG) z MagentaTV/MagioTV
"""
import logging
from datetime import datetime, timedelta
from app.models.program import Program

logger = logging.getLogger(__name__)


class EPGService:
    """
    Služba pro získávání a správu programových dat (EPG)
    """

    def __init__(self, auth_service):
        """
        Inicializace služby pro programová data

        Args:
            auth_service (AuthService): Instance služby pro autentizaci
        """
        self.auth_service = auth_service
        self.session = auth_service.session
        self.base_url = auth_service.get_base_url()
        self.language = auth_service.language

    def get_epg(self, channel_id=None, days_back=1, days_forward=1):
        """
        Získání EPG (Electronic Program Guide) pro zadaný kanál nebo všechny kanály

        Args:
            channel_id (int, optional): ID kanálu nebo None pro všechny kanály
            days_back (int): Počet dní zpět
            days_forward (int): Počet dní dopředu

        Returns:
            dict: EPG data rozdělená podle kanálů nebo None v případě chyby
        """
        # Získání autorizačních hlaviček
        headers = self.auth_service.get_auth_headers()
        if not headers:
            return None

        # Časový rozsah pro EPG
        current_date = datetime.now()
        start_time = (current_date - timedelta(days=days_back)).strftime("%Y-%m-%dT00:00:00.000Z")
        end_time = (current_date + timedelta(days=days_forward)).strftime("%Y-%m-%dT23:59:59.000Z")

        # Vytvoření filtru podle toho, zda je zadáno ID kanálu
        if channel_id:
            filter_str = f"channel.id=={channel_id} and startTime=ge={start_time} and endTime=le={end_time}"
        else:
            # Import zde, abychom předešli cirkulárnímu importu
            from app.services.client_service import ClientService
            client = ClientService(self.auth_service.username, self.auth_service.password, self.language)
            # Získat seznam všech kanálů
            channels = client.get_channels()
            if not channels:
                return None

            channel_ids = [str(channel["id"]) for channel in channels]
            filter_str = f"channel.id=in=({','.join(channel_ids)}) and startTime=ge={start_time} and endTime=le={end_time}"

        params = {
            "filter": filter_str,
            "limit": 1000,
            "offset": 0,
            "lang": self.language.upper()
        }

        try:
            response = self.session.get(
                f"{self.base_url}/v2/television/epg",
                params=params,
                headers=headers,
                timeout=30
            ).json()

            if not response.get("success", True):
                logger.error(f"Chyba při získání EPG: {response.get('errorMessage', 'Neznámá chyba')}")
                return None

            # Zpracování EPG dat
            epg_data = {}

            for item in response.get("items", []):
                item_channel_id = item.get("channel", {}).get("id")
                if not item_channel_id:
                    continue

                # Vytvoření záznamu pro kanál
                if item_channel_id not in epg_data:
                    epg_data[item_channel_id] = []

                # Přidání programů
                for program in item.get("programs", []):
                    # Převod časových údajů z milisekund na sekundy
                    start_time = datetime.fromtimestamp(program["startTimeUTC"] / 1000)
                    end_time = datetime.fromtimestamp(program["endTimeUTC"] / 1000)

                    prog_info = program.get("program", {})
                    prog_value = prog_info.get("programValue", {})

                    # Vytvoření objektu Program
                    program_obj = Program(
                        schedule_id=program.get("scheduleId"),
                        title=prog_info.get("title", ""),
                        start_time=start_time.strftime("%Y-%m-%d %H:%M:%S"),
                        end_time=end_time.strftime("%Y-%m-%d %H:%M:%S"),
                        description=prog_info.get("description", ""),
                        duration=int((end_time - start_time).total_seconds()),
                        category=prog_info.get("programCategory", {}).get("desc", ""),
                        year=prog_value.get("creationYear"),
                        episode=prog_value.get("episodeId"),
                        images=prog_info.get("images", [])
                    )

                    epg_data[item_channel_id].append(program_obj.to_dict())

            return epg_data

        except Exception as e:
            logger.error(f"Chyba při získání EPG: {e}")
            return None

    def find_program_by_time(self, channel_id, start_timestamp, end_timestamp):
        """
        Vyhledání pořadu podle času začátku a konce

        Args:
            channel_id (int): ID kanálu
            start_timestamp (int): Čas začátku v Unix timestamp
            end_timestamp (int): Čas konce v Unix timestamp

        Returns:
            dict: Informace o nalezeném pořadu nebo None při chybě
        """
        # Získání autorizačních hlaviček
        headers = self.auth_service.get_auth_headers()
        if not headers:
            return None

        # Převod timestampů na datetime objekty
        start_time = datetime.fromtimestamp(start_timestamp)
        end_time = datetime.fromtimestamp(end_timestamp)

        # Formátování pro API
        start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%S")
        end_time_str = end_time.strftime("%Y-%m-%dT%H:%M:%S")

        # Filtr pro hledání pořadu
        filter_str = f"channel.id=={channel_id} and startTime=ge={start_time_str}.000Z and endTime=le={end_time_str}.000Z"
        params = {
            "filter": filter_str,
            "limit": 10,
            "offset": 0,
            "lang": self.language.upper()
        }

        try:
            epg_response = self.session.get(
                f"{self.base_url}/v2/television/epg",
                params=params,
                headers=headers,
                timeout=30
            ).json()

            if not epg_response.get("success", True) or not epg_response.get("items"):
                logger.error(
                    f"Chyba při hledání pořadu v EPG: {epg_response.get('errorMessage', 'Pořad nebyl nalezen')}")
                return None

            # Hledání pořadu, který odpovídá časovému rozsahu
            schedule_id = None
            program_data = None

            for item in epg_response.get("items", []):
                for program in item.get("programs", []):
                    prog_start = program["startTimeUTC"] / 1000
                    prog_end = program["endTimeUTC"] / 1000

                    if prog_start <= end_timestamp and prog_end >= start_timestamp:
                        schedule_id = program["scheduleId"]

                        # Převod časových údajů z milisekund na sekundy
                        start_time_prog = datetime.fromtimestamp(program["startTimeUTC"] / 1000)
                        end_time_prog = datetime.fromtimestamp(program["endTimeUTC"] / 1000)

                        prog_info = program.get("program", {})
                        prog_value = prog_info.get("programValue", {})

                        # Vytvoření objektu Program
                        program_obj = Program(
                            schedule_id=program.get("scheduleId"),
                            title=prog_info.get("title", ""),
                            start_time=start_time_prog.strftime("%Y-%m-%d %H:%M:%S"),
                            end_time=end_time_prog.strftime("%Y-%m-%d %H:%M:%S"),
                            description=prog_info.get("description", ""),
                            duration=int((end_time_prog - start_time_prog).total_seconds()),
                            category=prog_info.get("programCategory", {}).get("desc", ""),
                            year=prog_value.get("creationYear"),
                            episode=prog_value.get("episodeId"),
                            images=prog_info.get("images", [])
                        )

                        program_data = program_obj.to_dict()
                        break

                if schedule_id:
                    break

            return {
                "schedule_id": schedule_id,
                "program": program_data
            } if schedule_id else None

        except Exception as e:
            logger.error(f"Chyba při hledání pořadu podle času: {e}")
            return None