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

    def __init__(self, auth_service, epg_service, quality="p5", cache_service=None,
                 system_service=None, config_service=None, session_service=None):
        """
        Inicializace služby pro archiv

        Args:
            auth_service (AuthService): Instance služby pro autentizaci
            epg_service (EPGService): Instance služby pro EPG
            quality (str): Kvalita streamu (p1-p5, kde p5 je nejvyšší)
            cache_service (CacheService, optional): Instance služby pro cache
            system_service (SystemService, optional): Instance služby pro monitoring
            config_service (ConfigService, optional): Instance služby pro konfiguraci
            session_service (SessionService, optional): Instance služby pro HTTP komunikaci
        """
        super().__init__("catchup", auth_service)
        self.epg_service = epg_service

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

        # Načtení kvality streamu z konfigurace, pokud není zadána
        if quality is None and self.config_service:
            self.quality = self.config_service.get_value("QUALITY", "p5")
        else:
            self.quality = quality

        # Základní údaje pro žádosti
        self.device_name = auth_service.device_name
        self.device_type = auth_service.device_type

        # Konfigurace z ConfigService
        self.cache_timeout = self._get_cache_timeout()

        # Zaznamenání inicializace v SystemService
        if self.system_service:
            self.system_service.log_event(
                "catchup", "init",
                f"CatchupService inicializována (jazyk: {self.language}, kvalita: {self.quality})"
            )

    def _get_cache_timeout(self):
        """
        Získání timeout hodnoty pro cache catchup

        Returns:
            int: Timeout v sekundách
        """
        default_timeout = TIME_CONSTANTS.get("STREAM_TIMEOUT", 600)

        if self.config_service:
            return self.config_service.get_value("CATCHUP_CACHE_TIMEOUT", default_timeout)

        return default_timeout

    def get_catchup_stream_by_id(self, schedule_id):
        """
        Získání URL pro přehrávání archivu podle ID pořadu

        Args:
            schedule_id (int): ID pořadu v programu

        Returns:
            dict: Informace o streamu včetně URL nebo None v případě chyby
        """
        # Pokus o získání z cache, pokud je k dispozici
        if self.cache_service:
            stream_key = f"catchup_stream_{self.language}_{schedule_id}_{self.quality}"
            stream = self.cache_service.get_from_cache(
                stream_key,
                self._fetch_catchup_stream_by_id,
                schedule_id
            )
            if stream:
                if self.system_service:
                    self.system_service.log_event(
                        "catchup", "cache_hit_stream",
                        f"Catchup stream pro ID {schedule_id} načten z cache"
                    )
                return stream

        # Pokud není cache nebo v cache nejsou data, získáme je přímo
        return self._fetch_catchup_stream_by_id(schedule_id)

    def _fetch_catchup_stream_by_id(self, schedule_id):
        """
        Interní metoda pro získání URL pro přehrávání archivu podle ID pořadu

        Args:
            schedule_id (int): ID pořadu v programu

        Returns:
            dict: Informace o streamu včetně URL nebo None v případě chyby
        """
        # Získání autorizačních hlaviček
        headers = self._get_auth_headers()
        if not headers:
            if self.system_service:
                self.system_service.log_error(
                    "catchup", "Nelze získat autorizační hlavičky pro catchup stream"
                )
            return None

        try:
            # Kontrola typu ID a jeho konverze
            try:
                schedule_id = int(schedule_id)
            except (ValueError, TypeError):
                error_msg = f"Neplatné ID pořadu: {schedule_id}"
                self.logger.error(error_msg)
                if self.system_service:
                    self.system_service.log_error("catchup", error_msg)
                return None

            params = {
                "service": "ARCHIVE",
                "name": self.device_name,
                "devtype": self.device_type,
                "id": schedule_id,
                "prof": self.quality,
                "ecid": "",
                "drm": "widevine"
            }

            stream_headers = {
                **headers,
                "Accept": "*/*",
                "Referer": f"https://{self.language}go.magio.tv/"
            }

            # Použití session_service, pokud je k dispozici
            if self.session_service:
                response = self.session_service.get_json(
                    f"{self.base_url}/v2/television/stream-url",
                    params=params,
                    headers=stream_headers
                )
            else:
                response = self.session.get(
                    f"{self.base_url}/v2/television/stream-url",
                    params=params,
                    headers=stream_headers,
                    timeout=TIME_CONSTANTS["STREAM_TIMEOUT"]
                ).json()

            if not response:
                error_msg = "Prázdná odpověď z API při získávání stream URL"
                self.logger.error(error_msg)
                if self.system_service:
                    self.system_service.log_error("catchup", error_msg)
                return None

            if not response.get("success", False):
                error_msg = response.get('errorMessage', 'Neznámá chyba')
                self.logger.error(f"Chyba při získání catchup URL: {error_msg}")
                if self.system_service:
                    self.system_service.log_error(
                        "catchup", f"Chyba při získání catchup URL pro ID {schedule_id}: {error_msg}"
                    )
                return None

            # Kontrola, zda odpověď obsahuje URL
            if "url" not in response:
                error_msg = f"Odpověď neobsahuje URL pro catchup: {response}"
                self.logger.error(error_msg)
                if self.system_service:
                    self.system_service.log_error("catchup", error_msg)
                return None

            url = response["url"]

            # Kontrola URL
            if not url or not url.startswith("http"):
                error_msg = f"Neplatná URL pro catchup: {url}"
                self.logger.error(error_msg)
                if self.system_service:
                    self.system_service.log_error("catchup", error_msg)
                return None

            # Následování přesměrování pro získání skutečné URL
            headers_redirect = {
                "Host": urlparse(url).netloc,
                "User-Agent": self.auth_service.user_agent,
                "Authorization": f"Bearer {self.auth_service.access_token}",
                "Accept": "*/*",
                "Referer": f"https://{self.language}go.magio.tv/"
            }

            # Použití session_service pro redirect
            if self.session_service:
                redirect_url = self.session_service.get_redirect_url(url, headers_redirect)
                final_url = redirect_url if redirect_url else url
                content_type = "application/vnd.apple.mpegurl"  # Výchozí hodnota
            else:
                redirect_response = self.session.get(
                    url,
                    headers=headers_redirect,
                    allow_redirects=False,
                    timeout=TIME_CONSTANTS["STREAM_TIMEOUT"]
                )
                final_url = redirect_response.headers.get("location", url)
                content_type = redirect_response.headers.get("Content-Type", "application/vnd.apple.mpegurl")

            # Logování získání URL
            if self.system_service:
                self.system_service.log_event(
                    "catchup", "stream_url_obtained",
                    f"Získána URL pro catchup stream, ID: {schedule_id}"
                )

            # Vytvoření objektu Stream
            stream = Stream(
                url=final_url,
                headers=dict(headers_redirect),
                content_type=content_type,
                is_live=False
            )

            stream_dict = stream.to_dict()

            # Uložení výsledku do cache
            if self.cache_service:
                stream_key = f"catchup_stream_{self.language}_{schedule_id}_{self.quality}"
                self.cache_service.store_in_cache(
                    stream_key,
                    stream_dict,
                    cache_timeout=self.cache_timeout
                )
                if self.system_service:
                    self.system_service.log_event(
                        "catchup", "cache_update_stream",
                        f"Catchup stream pro ID {schedule_id} uložen do cache"
                    )

            return stream_dict

        except Exception as e:
            error_msg = f"Chyba při získání catchup URL: {e}"
            self.logger.error(error_msg)
            if self.system_service:
                self.system_service.log_error("catchup", error_msg)
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
        # Pokus o získání z cache, pokud je k dispozici
        if self.cache_service:
            time_key = f"catchup_time_{self.language}_{channel_id}_{start_timestamp}_{end_timestamp}_{self.quality}"
            stream = self.cache_service.get_from_cache(
                time_key,
                self._fetch_catchup_by_time,
                channel_id, start_timestamp, end_timestamp
            )
            if stream:
                if self.system_service:
                    self.system_service.log_event(
                        "catchup", "cache_hit_time",
                        f"Catchup stream podle času pro kanál {channel_id} načten z cache"
                    )
                return stream

        # Pokud není cache nebo v cache nejsou data, získáme je přímo
        return self._fetch_catchup_by_time(channel_id, start_timestamp, end_timestamp)

    def _fetch_catchup_by_time(self, channel_id, start_timestamp, end_timestamp):
        """
        Interní metoda pro získání URL pro přehrávání archivu podle času

        Args:
            channel_id (int): ID kanálu
            start_timestamp (int): Čas začátku v Unix timestamp
            end_timestamp (int): Čas konce v Unix timestamp

        Returns:
            dict: Informace o streamu včetně URL nebo None v případě chyby
        """
        try:
            # Kontrola vstupních parametrů
            try:
                channel_id = int(channel_id)
                start_timestamp = int(float(start_timestamp))
                end_timestamp = int(float(end_timestamp))
            except (ValueError, TypeError) as e:
                error_msg = f"Neplatné parametry pro catchup podle času: {e}"
                self.logger.error(error_msg)
                if self.system_service:
                    self.system_service.log_error("catchup", error_msg)
                return None

            # Logování požadavku
            if self.system_service:
                start_time = datetime.fromtimestamp(start_timestamp).strftime('%Y-%m-%d %H:%M:%S')
                end_time = datetime.fromtimestamp(end_timestamp).strftime('%Y-%m-%d %H:%M:%S')
                self.system_service.log_event(
                    "catchup", "request_by_time",
                    f"Požadavek na catchup pro kanál {channel_id} od {start_time} do {end_time}"
                )

            # Nejprve najdeme program podle času
            program_info = self.epg_service.find_program_by_time(channel_id, start_timestamp, end_timestamp)
            if not program_info:
                error_msg = f"Nebyla vrácena žádná informace o programu pro kanál {channel_id} v daném čase"
                self.logger.error(error_msg)
                if self.system_service:
                    self.system_service.log_error("catchup", error_msg)
                return None

            if not program_info.get("schedule_id"):
                error_msg = "Pořad byl nalezen, ale neobsahuje schedule_id"
                self.logger.error(error_msg)
                if self.system_service:
                    self.system_service.log_error(
                        "catchup",
                        f"Pořad pro kanál {channel_id} v čase {start_timestamp}-{end_timestamp} neobsahuje schedule_id"
                    )
                return None

            # Použijeme ID pořadu pro získání streamu
            schedule_id = program_info["schedule_id"]

            # Logování nalezení programu
            if self.system_service and program_info.get("program"):
                program_title = program_info["program"].get("title", "Neznámý program")
                self.system_service.log_event(
                    "catchup", "program_found",
                    f"Nalezen program '{program_title}' (ID: {schedule_id}) pro catchup podle času"
                )

            stream = self.get_catchup_stream_by_id(schedule_id)

            if not stream:
                error_msg = f"Nepodařilo se získat stream pro nalezený program s ID {schedule_id}"
                self.logger.error(error_msg)
                if self.system_service:
                    self.system_service.log_error("catchup", error_msg)
                return None

            # Uložení výsledku do cache
            if self.cache_service:
                time_key = f"catchup_time_{self.language}_{channel_id}_{start_timestamp}_{end_timestamp}_{self.quality}"
                self.cache_service.store_in_cache(
                    time_key,
                    stream,
                    cache_timeout=self.cache_timeout
                )
                if self.system_service:
                    self.system_service.log_event(
                        "catchup", "cache_update_time",
                        f"Catchup stream podle času pro kanál {channel_id} uložen do cache"
                    )

            return stream

        except Exception as e:
            error_msg = f"Chyba při získání catchup podle času: {e}"
            self.logger.error(error_msg)
            if self.system_service:
                self.system_service.log_error("catchup", error_msg)
            return None

    def get_catchup_availability(self, channel_id):
        """
        Zjištění dostupnosti archivu pro daný kanál

        Args:
            channel_id (int): ID kanálu

        Returns:
            dict: Informace o dostupnosti archivu nebo None při chybě
        """
        # Pokus o získání z cache, pokud je k dispozici
        if self.cache_service:
            availability_key = f"catchup_availability_{self.language}_{channel_id}"
            availability = self.cache_service.get_from_cache(
                availability_key,
                self._fetch_catchup_availability,
                channel_id
            )
            if availability:
                if self.system_service:
                    self.system_service.log_event(
                        "catchup", "cache_hit_availability",
                        f"Dostupnost archivu pro kanál {channel_id} načtena z cache"
                    )
                return availability

        # Pokud není cache nebo v cache nejsou data, získáme je přímo
        return self._fetch_catchup_availability(channel_id)

    def _fetch_catchup_availability(self, channel_id):
        """
        Interní metoda pro zjištění dostupnosti archivu

        Args:
            channel_id (int): ID kanálu

        Returns:
            dict: Informace o dostupnosti archivu nebo None při chybě
        """
        try:
            # Kontrola vstupních parametrů
            try:
                channel_id = int(channel_id)
            except (ValueError, TypeError) as e:
                error_msg = f"Neplatné ID kanálu pro zjištění dostupnosti archivu: {e}"
                self.logger.error(error_msg)
                if self.system_service:
                    self.system_service.log_error("catchup", error_msg)
                return None

            # Získání dnů zpět z konfigurace
            days_back = 7
            if self.config_service:
                days_back = self.config_service.get_value("CATCHUP_DAYS_BACK", 7)

            # Logování požadavku
            if self.system_service:
                self.system_service.log_event(
                    "catchup", "availability_request",
                    f"Zjišťování dostupnosti archivu pro kanál {channel_id} (dnů zpět: {days_back})"
                )

            # Získání dat z EPG pro posledních X dní
            epg_data = self.epg_service.get_epg(channel_id, days_back=days_back, days_forward=0)

            if not epg_data:
                error_msg = f"Nepodařilo se získat EPG data pro kanál {channel_id}"
                self.logger.error(error_msg)
                if self.system_service:
                    self.system_service.log_error("catchup", error_msg)
                availability = {
                    "has_archive": False,
                    "days_available": 0,
                    "programs_count": 0,
                    "error": "Nepodařilo se získat EPG data"
                }
            elif not epg_data.get(channel_id):
                error_msg = f"EPG data neobsahují informace pro kanál {channel_id}"
                self.logger.error(error_msg)
                if self.system_service:
                    self.system_service.log_error("catchup", error_msg)
                availability = {
                    "has_archive": False,
                    "days_available": 0,
                    "programs_count": 0,
                    "error": "Kanál nemá žádná EPG data"
                }
            else:
                # Počet programů v archivu
                programs_count = len(epg_data[channel_id])

                # Zjištění nejstaršího dostupného programu
                oldest_timestamp = None
                newest_timestamp = None
                now = datetime.now().timestamp()

                for program in epg_data[channel_id]:
                    try:
                        program_start = datetime.strptime(program["start_time"], "%Y-%m-%d %H:%M:%S").timestamp()
                        if oldest_timestamp is None or program_start < oldest_timestamp:
                            oldest_timestamp = program_start
                        if newest_timestamp is None or program_start > newest_timestamp:
                            newest_timestamp = program_start
                    except (ValueError, KeyError) as e:
                        self.logger.warning(f"Chyba při zpracování času programu: {e}")
                        continue

                # Výpočet počtu dní v archivu
                days_available = (now - oldest_timestamp) / (24 * 3600) if oldest_timestamp else 0

                # Ošetření extrémních hodnot
                if days_available > 30:  # Pokud je to více než 30 dní, pravděpodobně jde o chybu
                    days_available = 7  # Nastavíme na typickou hodnotu

                # Přidání informace o časovém rozsahu
                oldest_date = datetime.fromtimestamp(oldest_timestamp).strftime(
                    '%Y-%m-%d %H:%M:%S') if oldest_timestamp else None
                newest_date = datetime.fromtimestamp(newest_timestamp).strftime(
                    '%Y-%m-%d %H:%M:%S') if newest_timestamp else None

                availability = {
                    "has_archive": programs_count > 0,
                    "days_available": round(days_available, 1),
                    "programs_count": programs_count,
                    "oldest_program": oldest_date,
                    "newest_program": newest_date
                }

                # Logování výsledku
                if self.system_service:
                    self.system_service.log_event(
                        "catchup", "availability_result",
                        f"Archiv pro kanál {channel_id}: {'dostupný' if availability['has_archive'] else 'nedostupný'}, "
                        f"dnů: {availability['days_available']}, programů: {programs_count}"
                    )

            # Uložení výsledku do cache
            if self.cache_service:
                availability_key = f"catchup_availability_{self.language}_{channel_id}"
                # Používáme delší dobu platnosti pro dostupnost archivu
                availability_timeout = self.cache_timeout * 2
                self.cache_service.store_in_cache(
                    availability_key,
                    availability,
                    cache_timeout=availability_timeout
                )
                if self.system_service:
                    self.system_service.log_event(
                        "catchup", "cache_update_availability",
                        f"Dostupnost archivu pro kanál {channel_id} uložena do cache"
                    )

            return availability

        except Exception as e:
            error_msg = f"Chyba při zjišťování dostupnosti archivu: {e}"
            self.logger.error(error_msg)
            if self.system_service:
                self.system_service.log_error("catchup", error_msg)
            # Vracíme základní strukturu, ale s označením chyby
            return {
                "has_archive": False,
                "days_available": 0,
                "programs_count": 0,
                "error": str(e)
            }

    def get_program_catchup(self, program_id):
        """
        Získání streamu pro konkrétní program

        Args:
            program_id (int): ID programu v EPG

        Returns:
            dict: Informace o streamu nebo None při chybě
        """
        # Tato metoda je pouze wrapper kolem get_catchup_stream_by_id
        return self.get_catchup_stream_by_id(program_id)

    def get_timeshift_window(self, channel_id):
        """
        Získání časového okna pro timeshift (posun času) kanálu

        Args:
            channel_id (int): ID kanálu

        Returns:
            dict: Informace o dostupném časovém okně pro timeshift
        """
        # Pokus o získání z cache, pokud je k dispozici
        if self.cache_service:
            window_key = f"timeshift_window_{self.language}_{channel_id}"
            window = self.cache_service.get_from_cache(
                window_key,
                self._fetch_timeshift_window,
                channel_id
            )
            if window:
                if self.system_service:
                    self.system_service.log_event(
                        "catchup", "cache_hit_timeshift",
                        f"Timeshift okno pro kanál {channel_id} načteno z cache"
                    )
                return window

        # Pokud není cache nebo v cache nejsou data, získáme je přímo
        return self._fetch_timeshift_window(channel_id)

    def _fetch_timeshift_window(self, channel_id):
        """
        Interní metoda pro získání časového okna pro timeshift

        Args:
            channel_id (int): ID kanálu

        Returns:
            dict: Informace o dostupném časovém okně pro timeshift
        """
        try:
            # Kontrola vstupních parametrů
            try:
                channel_id = int(channel_id)
            except (ValueError, TypeError) as e:
                error_msg = f"Neplatné ID kanálu pro timeshift okno: {e}"
                self.logger.error(error_msg)
                if self.system_service:
                    self.system_service.log_error("catchup", error_msg)
                return None

            # Logování požadavku
            if self.system_service:
                self.system_service.log_event(
                    "catchup", "timeshift_request",
                    f"Zjišťování timeshift okna pro kanál {channel_id}"
                )

            # Získání dat dostupnosti archivu
            availability = self.get_catchup_availability(channel_id)

            now = datetime.now()
            if not availability:
                error_msg = f"Nepodařilo se získat informace o dostupnosti archivu pro kanál {channel_id}"
                self.logger.error(error_msg)
                if self.system_service:
                    self.system_service.log_error("catchup", error_msg)
                window = {
                    "start_time": now.timestamp(),
                    "end_time": now.timestamp(),
                    "duration_hours": 0,
                    "available": False,
                    "error": "Nepodařilo se získat informace o dostupnosti archivu"
                }
            elif not availability.get("has_archive", False):
                window = {
                    "start_time": now.timestamp(),
                    "end_time": now.timestamp(),
                    "duration_hours": 0,
                    "available": False,
                    "reason": "Kanál nemá archiv"
                }
            else:
                # Výpočet časového okna
                days_available = availability.get("days_available", 0)

                # Ošetření extrémních hodnot
                if days_available > 30:  # Pokud je to více než 30 dní, pravděpodobně jde o chyba
                    days_available = 7  # Nastavíme na typickou hodnotu

                # Výpočet času začátku
                start_time = now - timedelta(days=days_available)

                # Formáty časů pro lepší čitelnost
                start_time_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
                end_time_str = now.strftime('%Y-%m-%d %H:%M:%S')

                window = {
                    "start_time": start_time.timestamp(),
                    "end_time": now.timestamp(),
                    "duration_hours": days_available * 24,
                    "available": True,
                    "start_time_formatted": start_time_str,
                    "end_time_formatted": end_time_str,
                    "programs_count": availability.get("programs_count", 0)
                }

                # Logování výsledku
                if self.system_service:
                    self.system_service.log_event(
                        "catchup", "timeshift_result",
                        f"Timeshift okno pro kanál {channel_id}: od {start_time_str} do {end_time_str}, "
                        f"trvání: {days_available:.1f} dnů"
                    )

            # Uložení výsledku do cache
            if self.cache_service:
                window_key = f"timeshift_window_{self.language}_{channel_id}"
                # Používáme delší dobu platnosti pro timeshift window
                window_timeout = self.cache_timeout * 2
                self.cache_service.store_in_cache(
                    window_key,
                    window,
                    cache_timeout=window_timeout
                )
                if self.system_service:
                    self.system_service.log_event(
                        "catchup", "cache_update_timeshift",
                        f"Timeshift okno pro kanál {channel_id} uloženo do cache"
                    )

            return window

        except Exception as e:
            error_msg = f"Chyba při zjišťování timeshift okna: {e}"
            self.logger.error(error_msg)
            if self.system_service:
                self.system_service.log_error("catchup", error_msg)
            # Vracíme základní strukturu, ale s označením chyby
            now = datetime.now()
            return {
                "start_time": now.timestamp(),
                "end_time": now.timestamp(),
                "duration_hours": 0,
                "available": False,
                "error": str(e)
            }

    def get_program_detail(self, program_id):
        """
        Získání detailních informací o programu

        Args:
            program_id (int): ID programu v EPG

        Returns:
            dict: Detailní informace o programu nebo None při chybě
        """
        # Pokus o získání z cache, pokud je k dispozici
        if self.cache_service:
            detail_key = f"program_detail_{self.language}_{program_id}"
            detail = self.cache_service.get_from_cache(
                detail_key,
                self._fetch_program_detail,
                program_id
            )
            if detail:
                if self.system_service:
                    self.system_service.log_event(
                        "catchup", "cache_hit_program_detail",
                        f"Detail programu {program_id} načten z cache"
                    )
                return detail

        # Pokud není cache nebo v cache nejsou data, získáme je přímo
        return self._fetch_program_detail(program_id)

    def _fetch_program_detail(self, program_id):
        """
        Interní metoda pro získání detailních informací o programu

        Args:
            program_id (int): ID programu v EPG

        Returns:
            dict: Detailní informace o programu nebo None při chybě
        """
        try:
            # Kontrola vstupních parametrů
            try:
                program_id = int(program_id)
            except (ValueError, TypeError) as e:
                error_msg = f"Neplatné ID programu: {e}"
                self.logger.error(error_msg)
                if self.system_service:
                    self.system_service.log_error("catchup", error_msg)
                return None

            # Získání autorizačních hlaviček
            headers = self._get_auth_headers()
            if not headers:
                if self.system_service:
                    self.system_service.log_error(
                        "catchup", "Nelze získat autorizační hlavičky pro detail programu"
                    )
                return None

            # Logování požadavku
            if self.system_service:
                self.system_service.log_event(
                    "catchup", "program_detail_request",
                    f"Zjišťování detailu programu {program_id}"
                )

            # Parametry požadavku
            params = {
                "languageCode": self.language.upper(),
                "id": program_id
            }

            # Použití session_service, pokud je k dispozici
            if self.session_service:
                response = self.session_service.get_json(
                    f"{self.base_url}/v2/television/program-details",
                    params=params,
                    headers=headers
                )
            else:
                response = self.session.get(
                    f"{self.base_url}/v2/television/program-details",
                    params=params,
                    headers=headers,
                    timeout=TIME_CONSTANTS["DEFAULT_TIMEOUT"]
                ).json()

            if not response or not response.get("success", False):
                error_msg = response.get('errorMessage', 'Neznámá chyba') if response else "Žádná odpověď z API"
                self.logger.error(f"Chyba při získání detailu programu: {error_msg}")
                if self.system_service:
                    self.system_service.log_error(
                        "catchup", f"Chyba při získání detailu programu {program_id}: {error_msg}"
                    )
                return None

            # Zpracování odpovědi
            program_data = response.get("program", {})

            # Formátování výsledku
            result = {
                "id": program_id,
                "title": program_data.get("title", ""),
                "original_title": program_data.get("originalTitle", ""),
                "description": program_data.get("description", ""),
                "start_time": None,  # Doplníme později, pokud je dostupné
                "end_time": None,  # Doplníme později, pokud je dostupné
                "duration": program_data.get("duration", 0),
                "category": program_data.get("programCategory", {}).get("desc", ""),
                "year": program_data.get("programValue", {}).get("creationYear"),
                "country": program_data.get("programValue", {}).get("originCountry", []),
                "images": program_data.get("images", []),
                "directors": [],
                "actors": [],
                "has_catchup": program_data.get("hasCatchUp", False)
            }

            # Zpracování tvůrců (directors, actors)
            for person in program_data.get("people", []):
                role = person.get("role", "").lower()
                name = person.get("name", "")
                if name:
                    if role == "director":
                        result["directors"].append(name)
                    elif role == "actor":
                        result["actors"].append(name)

            # Zpracování časů, pokud jsou dostupné
            schedule = response.get("schedule", {})
            if schedule:
                start_time_utc = schedule.get("startTimeUTC")
                end_time_utc = schedule.get("endTimeUTC")

                if start_time_utc:
                    start_time = datetime.fromtimestamp(start_time_utc / 1000)
                    result["start_time"] = start_time.strftime("%Y-%m-%d %H:%M:%S")

                if end_time_utc:
                    end_time = datetime.fromtimestamp(end_time_utc / 1000)
                    result["end_time"] = end_time.strftime("%Y-%m-%d %H:%M:%S")

            # Logování výsledku
            if self.system_service:
                self.system_service.log_event(
                    "catchup", "program_detail_result",
                    f"Získán detail programu '{result['title']}' (ID: {program_id})"
                )

            # Uložení výsledku do cache
            if self.cache_service:
                detail_key = f"program_detail_{self.language}_{program_id}"
                self.cache_service.store_in_cache(
                    detail_key,
                    result,
                    cache_timeout=self.cache_timeout * 2  # Delší platnost pro detaily programů
                )
                if self.system_service:
                    self.system_service.log_event(
                        "catchup", "cache_update_program_detail",
                        f"Detail programu {program_id} uložen do cache"
                    )

            return result

        except Exception as e:
            error_msg = f"Chyba při získání detailu programu: {e}"
            self.logger.error(error_msg)
            if self.system_service:
                self.system_service.log_error("catchup", error_msg)
            return None

    def get_catchup_programs(self, channel_id, start_date=None, end_date=None, limit=50):
        """
        Získání seznamu programů v archivu pro daný kanál v zadaném časovém rozmezí

        Args:
            channel_id (int): ID kanálu
            start_date (datetime, optional): Počáteční datum/čas nebo None pro dnešní den 00:00
            end_date (datetime, optional): Koncové datum/čas nebo None pro dnešní den 23:59
            limit (int, optional): Maximální počet programů

        Returns:
            list: Seznam programů v archivu nebo prázdný seznam při chybě
        """
        # Pokus o získání z cache, pokud je k dispozici
        cache_key = None
        if self.cache_service:
            # Formátování dat pro klíč cache
            start_str = start_date.strftime('%Y%m%d%H%M') if start_date else "today"
            end_str = end_date.strftime('%Y%m%d%H%M') if end_date else "today"
            cache_key = f"catchup_programs_{self.language}_{channel_id}_{start_str}_{end_str}_{limit}"

            programs = self.cache_service.get_from_cache(
                cache_key,
                self._fetch_catchup_programs,
                channel_id, start_date, end_date, limit
            )
            if programs is not None:  # Pozor: prázdný seznam je také platný výsledek
                if self.system_service:
                    self.system_service.log_event(
                        "catchup", "cache_hit_programs",
                        f"Seznam programů v archivu pro kanál {channel_id} načten z cache"
                    )
                return programs

        # Pokud není cache nebo v cache nejsou data, získáme je přímo
        return self._fetch_catchup_programs(channel_id, start_date, end_date, limit)

    def _fetch_catchup_programs(self, channel_id, start_date=None, end_date=None, limit=50):
        """
        Interní metoda pro získání seznamu programů v archivu

        Args:
            channel_id (int): ID kanálu
            start_date (datetime, optional): Počáteční datum/čas nebo None pro dnešní den 00:00
            end_date (datetime, optional): Koncové datum/čas nebo None pro dnešní den 23:59
            limit (int, optional): Maximální počet programů

        Returns:
            list: Seznam programů v archivu nebo prázdný seznam při chybě
        """
        try:
            # Kontrola vstupních parametrů
            try:
                channel_id = int(channel_id)
                limit = int(limit)
                if limit <= 0:
                    limit = 50
            except (ValueError, TypeError) as e:
                error_msg = f"Neplatné vstupní parametry pro získání programů v archivu: {e}"
                self.logger.error(error_msg)
                if self.system_service:
                    self.system_service.log_error("catchup", error_msg)
                return []

            # Výchozí časové období - dnešní den
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            if start_date is None:
                start_date = today
            if end_date is None:
                end_date = today.replace(hour=23, minute=59, second=59)

            # Převod na timestamp
            start_timestamp = start_date.timestamp()
            end_timestamp = end_date.timestamp()

            # Logování požadavku
            if self.system_service:
                self.system_service.log_event(
                    "catchup", "programs_request",
                    f"Získávání programů v archivu pro kanál {channel_id} "
                    f"od {start_date.strftime('%Y-%m-%d %H:%M')} do {end_date.strftime('%Y-%m-%d %H:%M')}"
                )

            # Použití EPG služby pro získání programů
            epg_data = self.epg_service.get_epg(channel_id, days_back=7, days_forward=0)

            if not epg_data or not epg_data.get(channel_id):
                if self.system_service:
                    self.system_service.log_error(
                        "catchup", f"Nepodařilo se získat EPG data pro kanál {channel_id}"
                    )
                return []

            # Filtrování programů podle časového období
            all_programs = epg_data[channel_id]

            if not all_programs:
                if self.system_service:
                    self.system_service.log_error(
                        "catchup", f"Žádné programy v EPG pro kanál {channel_id}"
                    )
                return []

            filtered_programs = []
            for program in all_programs:
                try:
                    prog_start = datetime.strptime(program["start_time"], "%Y-%m-%d %H:%M:%S").timestamp()
                    prog_end = datetime.strptime(program["end_time"], "%Y-%m-%d %H:%M:%S").timestamp()

                    # Program končí po začátku období a začíná před koncem období
                    if prog_end >= start_timestamp and prog_start <= end_timestamp:
                        # Přidání informace, zda je program aktuálně vysílán
                        now = datetime.now().timestamp()
                        program["is_current"] = (prog_start <= now and prog_end >= now)

                        # Přidání informace, zda je program již ukončen (pro archiv)
                        program["is_finished"] = (prog_end < now)

                        # Přidání informace o dostupnosti v archivu
                        # Pokud již skončil a není starší než 7 dní, je v archivu
                        max_archive_days = 7
                        if self.config_service:
                            max_archive_days = self.config_service.get_value("CATCHUP_DAYS_BACK", 7)

                        oldest_archive_time = now - (max_archive_days * 24 * 3600)
                        program["is_in_archive"] = (prog_end < now and prog_start >= oldest_archive_time)

                        # Přidání do výsledného seznamu
                        filtered_programs.append(program)
                except (ValueError, KeyError) as e:
                    self.logger.warning(f"Chyba při zpracování programu: {e}")
                    continue

            # Seřazení podle času začátku
            filtered_programs.sort(key=lambda x: x["start_time"])

            # Omezení počtu programů
            result_programs = filtered_programs[:limit]

            # Logování výsledku
            if self.system_service:
                self.system_service.log_event(
                    "catchup", "programs_result",
                    f"Získáno {len(result_programs)} programů v archivu pro kanál {channel_id}"
                )

            # Uložení výsledku do cache
            if self.cache_service:
                # Formátování dat pro klíč cache
                start_str = start_date.strftime('%Y%m%d%H%M') if start_date else "today"
                end_str = end_date.strftime('%Y%m%d%H%M') if end_date else "today"
                cache_key = f"catchup_programs_{self.language}_{channel_id}_{start_str}_{end_str}_{limit}"

                self.cache_service.store_in_cache(
                    cache_key,
                    result_programs,
                    cache_timeout=3600  # Kratší doba platnosti - 1 hodina
                )
                if self.system_service:
                    self.system_service.log_event(
                        "catchup", "cache_update_programs",
                        f"Seznam programů v archivu pro kanál {channel_id} uložen do cache"
                    )

            return result_programs

        except Exception as e:
            error_msg = f"Chyba při získání programů v archivu: {e}"
            self.logger.error(error_msg)
            if self.system_service:
                self.system_service.log_error("catchup", error_msg)
            return []

    def clear_cache(self):
        """
        Vyčištění cache pro catchup

        Returns:
            bool: True pokud bylo čištění úspěšné
        """
        if not self.cache_service:
            return False

        try:
            # Vyčištění všech cache záznamů souvisejících s catchup
            self.cache_service.clear_cache(f"catchup_stream_{self.language}_*")
            self.cache_service.clear_cache(f"catchup_time_{self.language}_*")
            self.cache_service.clear_cache(f"catchup_availability_{self.language}_*")
            self.cache_service.clear_cache(f"timeshift_window_{self.language}_*")
            self.cache_service.clear_cache(f"program_detail_{self.language}_*")
            self.cache_service.clear_cache(f"catchup_programs_{self.language}_*")

            if self.system_service:
                self.system_service.log_event(
                    "catchup", "cache_clear",
                    "Cache catchup byla vyčištěna"
                )

            return True

        except Exception as e:
            error_msg = f"Chyba při čištění cache catchup: {e}"
            self.logger.error(error_msg)
            if self.system_service:
                self.system_service.log_error("catchup", error_msg)
            return False