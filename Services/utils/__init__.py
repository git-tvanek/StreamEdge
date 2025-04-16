#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utility module for MagentaTV/MagioTV services

This module provides utility functions and constants used by the services.
"""

from Services.utils.http_client import MagentaHTTPClient
from Services.utils.constants import (
    BASE_URLS,
    DEVICE_TYPES,
    DEFAULT_USER_AGENT,
    STREAM_QUALITY,
    API_ENDPOINTS,
    TIME_CONSTANTS
)

# Export all utilities
__all__ = [
    'MagentaHTTPClient',
    'BASE_URLS',
    'DEVICE_TYPES',
    'DEFAULT_USER_AGENT',
    'STREAM_QUALITY',
    'API_ENDPOINTS',
    'TIME_CONSTANTS'
]