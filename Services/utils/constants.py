#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Konstanty používané napříč službami MagentaTV/MagioTV API
"""

# Základní URL podle jazyka
BASE_URLS = {
    "cz": "https://czgo.magio.tv",
    "sk": "https://skgo.magio.tv"
}

# Typy zařízení
DEVICE_TYPES = {
    "MOBILE": "OTT_ANDROID",
    "TV": "OTT_STB",
    "PC": "OTT_PC",
    "TABLET": "OTT_IPAD"
}

# Výchozí User-Agent pro požadavky
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 MagioGO/4.0.21"

# Kvalita streamu
STREAM_QUALITY = {
    "p1": "Nízká (SD 360p)",
    "p2": "Střední (SD 480p)",
    "p3": "Vyšší (HD 720p)",
    "p4": "Vysoká (HD 1080p)",
    "p5": "Nejvyšší (HD 1080p+)"
}

# Endpoints pro API
API_ENDPOINTS = {
    "auth": {
        "init": "/v2/auth/init",
        "login": "/v2/auth/login",
        "tokens": "/v2/auth/tokens"
    },
    "channels": {
        "list": "/v2/television/channels",
        "categories": "/home/categories"
    },
    "stream": {
        "live": "/v2/television/stream-url"
    },
    "epg": {
        "guide": "/v2/television/epg"
    },
    "devices": {
        "list": "/v2/home/my-devices",
        "delete": "/home/deleteDevice"
    }
}

# Časové konstanty
TIME_CONSTANTS = {
    "TOKEN_REFRESH_BEFORE_EXPIRY": 60,  # Sekundy před vypršením tokenu pro obnovu
    "DEFAULT_TIMEOUT": 30,  # Výchozí timeout pro HTTP požadavky
    "STREAM_TIMEOUT": 10    # Timeout pro získání stream URL
}